"""Small in-process sliding-window rate limiter.

Limits are per backend instance. Nginx enforces an additional per-IP limit in front of all
instances (see nginx/nginx.conf).
"""

import time
from collections import defaultdict, deque

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.core.security import Principal, require_agent, require_user


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def reset(self) -> None:
        self._hits.clear()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        if not get_settings().rate_limit_enabled:
            return
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            retry = max(1, int(window_seconds - (now - hits[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Zu viele Anfragen – bitte kurz warten.",
                headers={"Retry-After": str(retry)},
            )
        hits.append(now)
        if len(self._hits) > 50_000:  # crude memory guard
            self._hits.clear()


limiter = RateLimiter()


def _ident(request: Request, principal: Principal | None) -> str:
    if principal is not None:
        return str(principal.user_id or principal.agent_token_id or principal.label)
    return request.client.host if request.client else "anon"


def user_rate_limit(bucket: str, limit: int, window_seconds: int = 60):
    """Dependency: authenticated user + per-user limit."""

    async def dependency(request: Request, principal: Annotated[Principal, Depends(require_user)]) -> Principal:
        limiter.check(f"{bucket}:{_ident(request, principal)}", limit, window_seconds)
        return principal

    return dependency


def agent_rate_limit(bucket: str, limit: int, window_seconds: int = 60):
    """Dependency: authenticated agent + per-token limit."""

    async def dependency(request: Request, principal: Annotated[Principal, Depends(require_agent)]) -> Principal:
        limiter.check(f"{bucket}:{_ident(request, principal)}", limit, window_seconds)
        return principal

    return dependency


def ip_rate_limit(bucket: str, limit: int, window_seconds: int = 60):
    async def dependency(request: Request) -> None:
        limiter.check(f"{bucket}:{_ident(request, None)}", limit, window_seconds)

    return dependency
