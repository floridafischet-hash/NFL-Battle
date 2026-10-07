"""Authentication & authorization.

* Users log in with username + password (managed inside the app). Passwords are stored as
  salted PBKDF2-SHA256 hashes. After login the client receives a signed access token (JWT, HS256)
  which it sends as ``Authorization: Bearer …``.
* There is no external machine access: results are researched by the built-in ChatGPT result agent
  (app.services.result_agent), which runs inside the backend and never authenticates over HTTP.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings, is_placeholder
from app.core.db import get_session
from app.models import User
from app.models.enums import Role

log = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
LAST_SEEN_THROTTLE = timedelta(minutes=5)
_PBKDF2 = "pbkdf2_sha256"


class AuthError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_401_UNAUTHORIZED):
        headers = {"WWW-Authenticate": "Bearer"} if code == status.HTTP_401_UNAUTHORIZED else None
        super().__init__(status_code=code, detail=detail, headers=headers)


@dataclass
class Principal:
    """Who performs an action. ``kind="agent"`` is only ever created internally for the ChatGPT
    result agent; HTTP requests always resolve to ``kind="user"``."""

    kind: Literal["user", "agent"]
    label: str
    roles: frozenset[str] = field(default_factory=frozenset)
    user: User | None = None
    ip: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.kind == "user" and Role.ADMIN.value in self.roles

    @property
    def user_id(self):
        return self.user.id if self.user else None


# --------------------------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------------------------


def hash_password(password: str) -> str:
    iterations = get_settings().password_hash_iterations
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{_PBKDF2}${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored.split("$")
        if algorithm != _PBKDF2:
            return False
        expected = base64.b64decode(digest_b64)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


# a valid hash used to keep login timing similar for unknown usernames
_DUMMY_HASH: str | None = None


def dummy_verify(password: str) -> None:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("dummy-password")
    verify_password(password, _DUMMY_HASH)


# --------------------------------------------------------------------------------------------
# Access tokens
# --------------------------------------------------------------------------------------------

_secret_cache: str | None = None


def signing_secret() -> str:
    """SECRET_KEY from the environment, or – if it is still a placeholder – a random key that is
    generated once and persisted in DATA_DIR/.secret_key (so tokens survive restarts)."""
    global _secret_cache
    settings = get_settings()
    if not is_placeholder(settings.secret_key) and len(settings.secret_key) >= 16:
        return settings.secret_key
    if _secret_cache is None:
        path = Path(settings.data_dir) / ".secret_key"
        if path.exists():
            _secret_cache = path.read_text().strip()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            _secret_cache = secrets.token_urlsafe(48)
            path.write_text(_secret_cache)
            path.chmod(0o600)
            log.warning("SECRET_KEY is a placeholder – generated a random key in %s", path)
    return _secret_cache


def create_access_token(user: User) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(days=settings.token_ttl_days)
    claims = {
        "sub": str(user.id),
        "ver": user.token_version,
        "role": user.role.value,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "typ": "access",
    }
    return jwt.encode(claims, signing_secret(), algorithm=JWT_ALGORITHM), expires


def decode_access_token(token: str) -> dict:
    try:
        claims = jwt.decode(
            token,
            signing_secret(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("Sitzung abgelaufen – bitte erneut anmelden")
    except jwt.PyJWTError:
        raise AuthError("Ungültige Anmeldung")
    if claims.get("typ") != "access":
        raise AuthError("Ungültige Anmeldung")
    return claims


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded[:64]
    return request.client.host if request.client else None


async def authenticate(token: str, session: AsyncSession, ip: str | None = None) -> Principal:
    now = datetime.now(UTC)
    claims = decode_access_token(token)
    try:
        user = await session.get(User, uuid.UUID(str(claims["sub"])))
    except ValueError:
        user = None
    if user is None or user.is_bot or claims.get("ver") != user.token_version:
        raise AuthError("Sitzung ungültig – bitte erneut anmelden")
    if not user.is_active:
        raise AuthError("Dein Zugang wurde gesperrt. Bitte wende dich an einen Admin.", status.HTTP_403_FORBIDDEN)
    if user.last_seen_at is None or now - user.last_seen_at > LAST_SEEN_THROTTLE:
        user.last_seen_at = now
        await session.commit()
    roles = frozenset({Role.USER.value, Role.ADMIN.value} if user.role == Role.ADMIN else {Role.USER.value})
    return Principal("user", user.display_name, roles, user, ip)


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthError("Anmeldung erforderlich")
    return token.strip()


async def get_principal(request: Request, session: Annotated[AsyncSession, Depends(get_session)]) -> Principal:
    principal = await authenticate(_bearer(request), session, client_ip(request))
    request.state.principal = principal
    return principal


async def require_user(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
    if principal.kind != "user":
        raise AuthError("Kein Benutzerzugang", status.HTTP_403_FORBIDDEN)
    return principal


async def require_admin(principal: Annotated[Principal, Depends(require_user)]) -> Principal:
    if not principal.is_admin:
        raise AuthError("Nur für Admins", status.HTTP_403_FORBIDDEN)
    return principal


CurrentUser = Annotated[Principal, Depends(require_user)]


async def require_superuser(principal: Annotated[Principal, Depends(require_admin)]) -> Principal:
    if principal.user is None or not principal.user.is_superuser:
        raise AuthError("Nur der Inhaber dieser Instanz darf Benutzer verwalten", status.HTTP_403_FORBIDDEN)
    return principal


CurrentAdmin = Annotated[Principal, Depends(require_admin)]
CurrentSuperuser = Annotated[Principal, Depends(require_superuser)]
DBSession = Annotated[AsyncSession, Depends(get_session)]
