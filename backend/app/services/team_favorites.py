from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserTeamFavorite


async def get_for_user(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    rows = await session.scalars(
        select(UserTeamFavorite.team_slug)
        .where(UserTeamFavorite.user_id == user_id)
        .order_by(UserTeamFavorite.position, UserTeamFavorite.team_slug)
    )
    return list(rows)


async def replace_for_user(session: AsyncSession, user_id: uuid.UUID, favorites: list[str]) -> None:
    await session.execute(delete(UserTeamFavorite).where(UserTeamFavorite.user_id == user_id))
    session.add_all(
        UserTeamFavorite(user_id=user_id, team_slug=team_slug, position=position)
        for position, team_slug in enumerate(favorites)
    )
