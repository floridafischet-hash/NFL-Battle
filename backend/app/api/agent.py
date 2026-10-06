"""OpenClaw agent API (role AGENT only). See docs/OPENCLAW.md."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.ratelimit import agent_rate_limit
from app.core.security import CurrentAgent, DBSession
from app.models import Match, Season
from app.models.enums import SeasonStatus
from app.services import agent as agent_service
from app.services.seasons import match_out, now_utc

router = APIRouter(prefix="/api/agent", tags=["agent"], dependencies=[Depends(agent_rate_limit("agent", 120, 60))])


async def _json(request: Request) -> Any:
    try:
        return await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"raw": (await request.body())[:2000].decode("utf-8", "replace")}


def _agent_match(m: Match) -> dict[str, Any]:
    out = match_out(m).model_dump(mode="json")
    out["result_check_requested"] = m.result_check_requested_at is not None
    return out


@router.get("/whoami")
async def whoami(agent: CurrentAgent) -> dict[str, Any]:
    return {"label": agent.label, "roles": sorted(agent.roles)}


@router.get("/matches")
async def matches(agent: CurrentAgent, session: DBSession) -> list[dict[str, Any]]:
    """All matches of the active season (e.g. to research the schedule)."""
    season = (await session.execute(select(Season).where(Season.status == SeasonStatus.ACTIVE))).scalar_one_or_none()
    if season is None:
        return []
    rows = (
        (await session.execute(select(Match).where(Match.season_id == season.id).order_by(Match.id))).unique().scalars()
    )
    return [_agent_match(m) for m in rows]


@router.get("/matches/pending")
async def pending(agent: CurrentAgent, session: DBSession) -> list[dict[str, Any]]:
    """Matches that need a result (kickoff passed or locked, not final) or were flagged by an admin."""
    rows = (
        (
            await session.execute(
                select(Match)
                .join(Season, Season.id == Match.season_id)
                .where(Season.status == SeasonStatus.ACTIVE, agent_service.pending_match_filter(now_utc()))
                .order_by(Match.kickoff_at.asc().nulls_last(), Match.id)
            )
        )
        .unique()
        .scalars()
    )
    return [_agent_match(m) for m in rows]


@router.post("/results")
async def post_result(request: Request, agent: CurrentAgent, session: DBSession) -> JSONResponse:
    code, body = await agent_service.process_result(session, agent, await _json(request))
    return JSONResponse(body, status_code=code)


@router.post("/schedule")
async def post_schedule(request: Request, agent: CurrentAgent, session: DBSession) -> JSONResponse:
    code, body = await agent_service.set_schedule(session, agent, await _json(request))
    return JSONResponse(body, status_code=code)


@router.post("/events")
async def post_event(request: Request, agent: CurrentAgent, session: DBSession) -> JSONResponse:
    code, body = await agent_service.post_event(session, agent, await _json(request))
    return JSONResponse(body, status_code=code)
