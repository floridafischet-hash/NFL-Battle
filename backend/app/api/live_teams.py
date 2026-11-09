from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.security import CurrentUser, DBSession
from app.services import nfl_live, team_favorites
from app.services.audit import audit

router = APIRouter(prefix="/api/live", tags=["live-nfl"])


@router.get("/teams")
async def live_teams(principal: CurrentUser, session: DBSession) -> dict[str, Any]:
    try:
        data = await nfl_live.teams()
        user = principal.user
        if user is None:
            raise HTTPException(status_code=401, detail="Anmeldung erforderlich")
        data["favorites"] = await team_favorites.get_for_user(session, user.id)
        return data
    except nfl_live.LiveDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class TeamFavoritesIn(BaseModel):
    favorites: list[str] = Field(max_length=32)

    @field_validator("favorites")
    @classmethod
    def _favorites(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip().lower() for value in values]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Favoriten dürfen nicht doppelt vorkommen")
        invalid = [value for value in cleaned if value not in nfl_live.NFL_TEAM_SLUGS]
        if invalid:
            raise ValueError("Unbekanntes NFL-Team")
        return cleaned


@router.put("/teams/favorites")
async def put_team_favorites(body: TeamFavoritesIn, principal: CurrentUser, session: DBSession) -> dict[str, list[str]]:
    user = principal.user
    if user is None:
        raise HTTPException(status_code=401, detail="Anmeldung erforderlich")
    old = await team_favorites.get_for_user(session, user.id)
    await team_favorites.replace_for_user(session, user.id, body.favorites)
    audit(
        session,
        principal,
        "LIVE_TEAM_FAVORITES_UPDATED",
        "user_team_favorites",
        str(user.id),
        {"favorites": old},
        {"favorites": body.favorites},
        source="WEB",
    )
    await session.commit()
    return {"favorites": body.favorites}


@router.get("/players/{athlete_id}")
async def live_player(athlete_id: str, principal: CurrentUser) -> dict[str, Any]:
    try:
        return await nfl_live.player_detail(athlete_id)
    except nfl_live.LiveDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/games")
async def live_regular_season_games(principal: CurrentUser, session: DBSession) -> dict[str, Any]:
    try:
        user = principal.user
        if user is None:
            raise HTTPException(status_code=401, detail="Anmeldung erforderlich")
        data = await nfl_live.regular_season_games()
        favorites = await team_favorites.get_for_user(session, user.id)
        standings = await nfl_live.conference_standings()
        standing_by_slug = {row["slug"]: row for row in standings}
        data["favorites"] = favorites
        data["favorite_standings"] = [standing_by_slug[slug] for slug in favorites if slug in standing_by_slug]
        return data
    except nfl_live.LiveDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/teams/{slug}")
async def live_team(slug: str, principal: CurrentUser) -> dict[str, Any]:
    try:
        return await nfl_live.team_detail(slug)
    except nfl_live.LiveDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
