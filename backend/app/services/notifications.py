from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, User
from app.models.enums import Role
from app.realtime.events import publish


async def notify(
    session: AsyncSession,
    user_ids: Iterable[uuid.UUID],
    type_: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> int:
    count = 0
    for user_id in set(user_ids):
        session.add(Notification(user_id=user_id, type=type_, title=title[:160], body=body, link=link))
        await publish(session, "notification", target_user_id=str(user_id))
        count += 1
    return count


async def active_user_ids(session: AsyncSession) -> list[uuid.UUID]:
    rows = await session.execute(select(User.id).where(User.is_active.is_(True), User.is_bot.is_(False)))
    return list(rows.scalars())


async def admin_user_ids(session: AsyncSession) -> list[uuid.UUID]:
    rows = await session.execute(
        select(User.id).where(User.is_active.is_(True), User.is_bot.is_(False), User.role == Role.ADMIN)
    )
    return list(rows.scalars())


async def notify_admins(
    session: AsyncSession, type_: str, title: str, body: str | None = None, link: str | None = None
) -> int:
    return await notify(session, await admin_user_ids(session), type_, title, body, link)


async def notify_all(
    session: AsyncSession, type_: str, title: str, body: str | None = None, link: str | None = None
) -> int:
    return await notify(session, await active_user_ids(session), type_, title, body, link)
