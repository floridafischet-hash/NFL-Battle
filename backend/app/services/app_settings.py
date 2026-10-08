"""Admin-editable settings for the dashboard greeting."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSetting

KING_NAME = "king_name"
KING_TITLE = "king_title"
INSTANCE_OWNER_USER_ID = "instance_owner_user_id"
DEFAULT_KING_TITLE = "König"


async def get_value(session: AsyncSession, key: str) -> str | None:
    row = await session.get(AppSetting, key)
    return row.value if row else None


async def set_value(session: AsyncSession, key: str, value: str | None) -> None:
    row = await session.get(AppSetting, key)
    if not value:
        if row is not None:
            await session.delete(row)
        return
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value


async def greeting(session: AsyncSession) -> dict[str, Any]:
    return {
        "king_name": await get_value(session, KING_NAME),
        "king_title": await get_value(session, KING_TITLE) or DEFAULT_KING_TITLE,
    }
