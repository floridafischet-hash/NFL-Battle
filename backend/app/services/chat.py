from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.models import ChatMessage, Upload
from app.models.enums import UploadKind
from app.realtime.events import publish
from app.services.audit import audit
from app.services.seasons import now_utc

MAX_BODY = 1000
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def serialize(message: ChatMessage) -> dict[str, Any]:
    deleted = message.deleted_at is not None
    system = message.system_message
    return {
        "id": message.id,
        "created_at": message.created_at.isoformat(),
        "user": {
            "id": str(message.user.id),
            "display_name": message.user.display_name,
            "avatar_url": message.user.avatar_url,
            "is_bot": message.user.is_bot,
        },
        "body": "" if deleted else message.body,
        "image_url": None if deleted or message.upload is None else message.upload.url,
        "deleted": deleted,
        "system": None if system is None else {"type": system.type.value, "payload": system.payload},
    }


async def list_messages(session: AsyncSession, before_id: int | None, limit: int) -> list[dict[str, Any]]:
    stmt = select(ChatMessage).order_by(ChatMessage.id.desc()).limit(limit)
    if before_id is not None:
        stmt = stmt.where(ChatMessage.id < before_id)
    rows = list((await session.execute(stmt)).unique().scalars())
    return [serialize(m) for m in reversed(rows)]


async def create_message(
    session: AsyncSession, principal: Principal, body: str, upload_id: uuid.UUID | None
) -> dict[str, Any]:
    assert principal.user is not None
    text = _CONTROL.sub("", body or "").strip()
    if len(text) > MAX_BODY:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Nachricht zu lang (max. {MAX_BODY} Zeichen).")
    upload = None
    if upload_id is not None:
        upload = await session.get(Upload, upload_id)
        if upload is None or upload.kind != UploadKind.CHAT or upload.uploaded_by != principal.user.id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Ungültiges Bild.")
    if not text and upload is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Leere Nachricht.")
    message = ChatMessage(user_id=principal.user.id, body=text, upload_id=upload.id if upload else None)
    session.add(message)
    await session.flush()
    await publish(session, "chat_message", id=message.id)
    await session.commit()
    message = (await session.execute(select(ChatMessage).where(ChatMessage.id == message.id))).unique().scalar_one()
    return serialize(message)


async def delete_message(session: AsyncSession, principal: Principal, message_id: int) -> None:
    message = await session.get(ChatMessage, message_id)
    if message is None or message.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nachricht nicht gefunden")
    if message.user_id != principal.user_id and not principal.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Du kannst nur eigene Nachrichten löschen.")
    message.deleted_at = now_utc()
    message.deleted_by = principal.user_id
    if principal.is_admin and message.user_id != principal.user_id:
        audit(
            session,
            principal,
            "CHAT_MESSAGE_DELETED",
            "chat_message",
            message.id,
            {"body": message.body[:500]},
            None,
            source="ADMIN",
        )
    await publish(session, "chat_message_deleted", id=message.id)
    await session.commit()
