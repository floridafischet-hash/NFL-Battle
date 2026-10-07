"""Chat, notifications, statistics, Hall of Fame and the realtime WebSocket."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from app.core.db import get_sessionmaker
from app.core.ratelimit import user_rate_limit
from app.core.security import AuthError, CurrentUser, DBSession, authenticate, decode_access_token
from app.models import Notification, User
from app.models.enums import UploadKind
from app.realtime.hub import Connection, hub
from app.services import chat, stats
from app.services.seasons import get_current_season, now_utc, resolve_season
from app.services.uploads import store_image

router = APIRouter(prefix="/api", tags=["social"])


class ChatIn(BaseModel):
    body: str = Field(default="", max_length=2000)
    upload_id: uuid.UUID | None = None


@router.get("/chat/messages")
async def chat_messages(
    principal: CurrentUser, session: DBSession, before: int | None = None, limit: int = Query(50, ge=1, le=100)
) -> list[dict[str, Any]]:
    return await chat.list_messages(session, before, limit)


@router.post(
    "/chat/messages", status_code=status.HTTP_201_CREATED, dependencies=[Depends(user_rate_limit("chat", 20, 60))]
)
async def post_chat_message(body: ChatIn, principal: CurrentUser, session: DBSession) -> dict[str, Any]:
    return await chat.create_message(session, principal, body.body, body.upload_id)


@router.post(
    "/chat/uploads",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_rate_limit("chat-upload", 10, 300))],
)
async def chat_upload(principal: CurrentUser, session: DBSession, file: UploadFile = File(...)) -> dict[str, Any]:
    upload = await store_image(session, file, UploadKind.CHAT, principal.user_id)
    await session.commit()
    return {"id": upload.id, "url": upload.url, "width": upload.width, "height": upload.height}


@router.delete("/chat/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_message(message_id: int, principal: CurrentUser, session: DBSession) -> None:
    await chat.delete_message(session, principal, message_id)


@router.get("/chat/online")
async def online(principal: CurrentUser, session: DBSession) -> list[dict[str, Any]]:
    ids = [uuid.UUID(i) for i in hub.online_user_ids()]
    if not ids:
        return []
    users = (await session.execute(select(User).where(User.id.in_(ids)))).scalars()
    return [{"id": u.id, "display_name": u.display_name, "avatar_url": u.avatar_url} for u in users]


# ------------------------------------------------------------------ notifications


@router.get("/notifications")
async def notifications(
    principal: CurrentUser, session: DBSession, limit: int = Query(30, ge=1, le=100)
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(Notification)
            .where(Notification.user_id == principal.user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
    ).scalars()
    unread = (
        await session.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == principal.user_id, Notification.read_at.is_(None)
            )
        )
    ).scalar_one()
    return {
        "unread": unread,
        "items": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "link": n.link,
                "read": n.read_at is not None,
                "created_at": n.created_at,
            }
            for n in rows
        ],
    }


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def read_notification(notification_id: int, principal: CurrentUser, session: DBSession) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == principal.user_id)
        .values(read_at=now_utc())
    )
    await session.commit()


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def read_all(principal: CurrentUser, session: DBSession) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == principal.user_id, Notification.read_at.is_(None))
        .values(read_at=now_utc())
    )
    await session.commit()


# ------------------------------------------------------------------ statistics & hall of fame


def _uid(value: str, principal) -> uuid.UUID:
    if value == "me":
        return principal.user_id
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Benutzer nicht gefunden")


@router.get("/stats/users/{user_id}")
async def user_stats(user_id: str, principal: CurrentUser, session: DBSession, season_id: int | None = None):
    uid = _uid(user_id, principal)
    season = await resolve_season(session, season_id, principal) if season_id else await get_current_season(session)
    return await stats.user_stats(session, uid, season.id if season else None)


@router.get("/stats/compare")
async def compare(principal: CurrentUser, session: DBSession, a: str, b: str, season_id: int | None = None):
    season = await resolve_season(session, season_id, principal)
    ua, ub = _uid(a, principal), _uid(b, principal)
    return await stats.compare_users(session, ua, ub, season.id)


@router.get("/stats/overview")
async def overview(principal: CurrentUser, session: DBSession, season_id: int | None = None):
    season = await resolve_season(session, season_id, principal)
    return await stats.season_overview(session, season.id)


@router.get("/hall-of-fame")
async def hall_of_fame(principal: CurrentUser, session: DBSession):
    return await stats.hall_of_fame(session)


@router.get("/users")
async def list_players(principal: CurrentUser, session: DBSession) -> list[dict[str, Any]]:
    users = (
        await session.execute(
            select(User).where(User.is_bot.is_(False), User.is_active.is_(True)).order_by(User.display_name)
        )
    ).scalars()
    return [
        {"id": u.id, "display_name": u.display_name, "avatar_url": u.avatar_url, "username": u.username} for u in users
    ]


# ------------------------------------------------------------------ websocket

ws_router = APIRouter()


WS_REVALIDATE_SECONDS = 60


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Realtime channel. The client sends {"type": "auth", "token": "..."} as its first message."""
    await websocket.accept()
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        first = json.loads(raw)
        token = first.get("token") if first.get("type") == "auth" else None
        if not token:
            raise AuthError("auth message expected")
        async with get_sessionmaker()() as session:
            principal = await authenticate(token, session)
        if principal.kind != "user" or principal.user is None:
            raise AuthError("only users")
        expires_at = float(decode_access_token(token)["exp"])
    except (TimeoutError, ValueError, AuthError, WebSocketDisconnect, json.JSONDecodeError):
        with contextlib.suppress(Exception):
            await websocket.close(code=4401)
        return

    conn = Connection(websocket, principal.user.id, principal.is_admin)
    hub.register(conn)
    await websocket.send_json({"type": "ready", "user_id": str(principal.user.id)})
    hub.broadcast({"type": "presence"})

    async def sender() -> None:
        while True:
            message = await conn.queue.get()
            await websocket.send_json(message)

    async def receiver() -> None:
        while True:
            data = await websocket.receive_text()
            if data == "ping" or '"ping"' in data:
                await websocket.send_json({"type": "pong"})

    async def expiry() -> None:
        # ends the connection when the token expires or the account was blocked, demoted or logged out
        while time.time() < expires_at:
            await asyncio.sleep(min(WS_REVALIDATE_SECONDS, max(1.0, expires_at - time.time())))
            try:
                async with get_sessionmaker()() as session:
                    current = await authenticate(token, session)
            except AuthError:
                return
            conn.is_admin = current.is_admin

    tasks = [asyncio.create_task(t()) for t in (sender, receiver, expiry)]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        hub.unregister(conn)
        hub.broadcast({"type": "presence"})
        with contextlib.suppress(Exception):
            await websocket.close(code=4401 if tasks[2].done() else 1000)
