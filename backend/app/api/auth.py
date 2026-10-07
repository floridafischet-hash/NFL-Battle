from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from app.core.ratelimit import ip_rate_limit, limiter, user_rate_limit
from app.core.security import (
    CurrentUser,
    DBSession,
    Principal,
    client_ip,
    create_access_token,
    dummy_verify,
    hash_password,
    verify_password,
)
from app.core.text import clean_display_name
from app.models import User
from app.models.enums import Role, UploadKind
from app.services.audit import audit
from app.services.uploads import store_image

router = APIRouter(prefix="/api", tags=["auth"])

MIN_PASSWORD = 6


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class MeOut(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None
    role: str
    is_admin: bool


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: MeOut


class ProfileIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        return None if v is None else clean_display_name(v)


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=MIN_PASSWORD, max_length=200)


def me_out(user: User) -> MeOut:
    return MeOut(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        role=user.role.value,
        is_admin=user.is_admin,
    )


@router.post("/auth/login", response_model=LoginOut, dependencies=[Depends(ip_rate_limit("login", 20, 300))])
async def login(body: LoginIn, request: Request, session: DBSession) -> LoginOut:
    username = body.username.strip().lower()
    ip = client_ip(request) or "?"
    # protection against guessing one account: only failed attempts count, per (account, IP) plus a
    # higher cap per account – so nobody can lock a friend out with a few wrong passwords
    keys = ((f"login-fail:{username}:{ip}", 10), (f"login-fail:{username}", 50))
    wait = max(limiter.blocked(key, limit, 900) for key, limit in keys)
    if wait:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Zu viele Fehlversuche – bitte später erneut versuchen.",
            headers={"Retry-After": str(wait)},
        )
    user = (
        await session.execute(select(User).where(func.lower(User.username) == username, User.is_bot.is_(False)))
    ).scalar_one_or_none()
    if user is None:
        await asyncio.to_thread(dummy_verify, body.password)
        ok = False
    else:
        ok = await asyncio.to_thread(verify_password, body.password, user.password_hash)
    if not ok or user is None:
        for key, _ in keys:
            limiter.record(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Benutzername oder Passwort falsch")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dein Zugang wurde gesperrt. Bitte wende dich an einen Admin.")
    user.last_login_at = datetime.now(UTC)
    token, expires = create_access_token(user)
    roles = frozenset({Role.USER.value, Role.ADMIN.value} if user.is_admin else {Role.USER.value})
    principal = Principal("user", user.display_name, roles, user, ip)
    audit(session, principal, "USER_LOGIN", "user", user.id, None, None, source="WEB")
    await session.commit()
    return LoginOut(access_token=token, expires_at=expires, user=me_out(user))


@router.get("/me", response_model=MeOut)
async def me(principal: CurrentUser) -> MeOut:
    assert principal.user is not None
    return me_out(principal.user)


@router.patch("/me", response_model=MeOut)
async def update_profile(body: ProfileIn, principal: CurrentUser, session: DBSession) -> MeOut:
    user = principal.user
    assert user is not None
    if body.display_name is not None:
        name = body.display_name
        if name != user.display_name:
            audit(
                session,
                principal,
                "PROFILE_UPDATED",
                "user",
                user.id,
                {"display_name": user.display_name},
                {"display_name": name},
            )
            user.display_name = name
    await session.commit()
    return me_out(user)


@router.post("/me/password", response_model=LoginOut, dependencies=[Depends(user_rate_limit("password", 5, 300))])
async def change_password(body: PasswordIn, principal: CurrentUser, session: DBSession) -> LoginOut:
    user = principal.user
    assert user is not None
    if not await asyncio.to_thread(verify_password, body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Das aktuelle Passwort ist falsch.")
    user.password_hash = await asyncio.to_thread(hash_password, body.new_password)
    user.token_version += 1  # logs out all other sessions
    audit(session, principal, "PASSWORD_CHANGED", "user", user.id, None, None)
    await session.commit()
    token, expires = create_access_token(user)
    return LoginOut(access_token=token, expires_at=expires, user=me_out(user))


@router.post("/me/avatar", response_model=MeOut, dependencies=[Depends(user_rate_limit("avatar", 10, 300))])
async def upload_avatar(principal: CurrentUser, session: DBSession, file: UploadFile = File(...)) -> MeOut:
    user = principal.user
    assert user is not None
    upload = await store_image(session, file, UploadKind.AVATAR, user.id)
    old = user.avatar_url
    user.avatar_url = upload.url
    audit(session, principal, "AVATAR_UPDATED", "user", user.id, {"avatar_url": old}, {"avatar_url": user.avatar_url})
    await session.commit()
    return me_out(user)


@router.delete("/me/avatar", response_model=MeOut)
async def delete_avatar(principal: CurrentUser, session: DBSession) -> MeOut:
    user = principal.user
    assert user is not None
    user.avatar_url = None
    await session.commit()
    return me_out(user)
