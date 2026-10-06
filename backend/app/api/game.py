"""Player-facing endpoints: seasons, matches, brackets, leaderboard, dashboard, change requests."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.ratelimit import user_rate_limit
from app.core.security import CurrentUser, DBSession, Principal
from app.models import Bracket, Leaderboard, Match, Prediction, PredictionChange, Score, Season, Team, User
from app.models.enums import ChangeRequestStatus, MatchStatus, SeasonStatus
from app.schemas.common import PickIn, SeasonOut, TeamOut
from app.schemas.serializers import change_request_out
from app.services import brackets as bracket_service
from app.services import change_requests
from app.services.bracket_engine import SLOTS
from app.services.scoring import leaderboard_rows
from app.services.seasons import (
    get_current_season,
    is_locked,
    match_out,
    not_found,
    now_utc,
    resolve_season,
    team_out,
)

router = APIRouter(prefix="/api", tags=["game"])
PickLimiter = Depends(user_rate_limit("pick", 120, 60))


@router.get("/seasons", response_model=list[SeasonOut])
async def list_seasons(principal: CurrentUser, session: DBSession) -> list[Season]:
    stmt = select(Season).order_by(Season.year.desc())
    if not principal.is_admin:
        stmt = stmt.where(Season.status != SeasonStatus.DRAFT)
    return list((await session.execute(stmt)).unique().scalars())


@router.get("/seasons/current", response_model=SeasonOut | None)
async def current_season(principal: CurrentUser, session: DBSession) -> Season | None:
    return await get_current_season(session)


@router.get("/teams", response_model=list[TeamOut])
async def list_teams(principal: CurrentUser, session: DBSession) -> list[Team]:
    return list((await session.execute(select(Team).order_by(Team.conference, Team.name))).scalars())


@router.get("/seasons/{season_id}/teams", response_model=list[TeamOut])
async def season_teams(season_id: int, principal: CurrentUser, session: DBSession) -> list[TeamOut]:
    ctx = await bracket_service.load_context(session, await resolve_season(session, season_id))
    seeds = ctx.seeds
    out = [team_out(st.team, seeds) for st in ctx.season_teams]
    return sorted([t for t in out if t], key=lambda t: (t.conference, t.seed or 99))


async def _my_picks(session, user_id: uuid.UUID, season_id: int) -> dict[int, Prediction]:
    rows = await session.execute(
        select(Prediction)
        .join(Bracket, Bracket.id == Prediction.bracket_id)
        .where(Bracket.user_id == user_id, Bracket.season_id == season_id)
    )
    return {p.match_id: p for p in rows.unique().scalars()}


def _pick_out(p: Prediction | None) -> dict[str, Any] | None:
    if p is None:
        return None
    return {"winner_team_id": p.winner_team_id, "winner_score": p.winner_score, "loser_score": p.loser_score}


@router.get("/seasons/{season_id}/matches")
async def season_matches(season_id: int, principal: CurrentUser, session: DBSession) -> list[dict[str, Any]]:
    season = await resolve_season(session, season_id)
    ctx = await bracket_service.load_context(session, season)
    assert principal.user is not None
    picks = await _my_picks(session, principal.user.id, season.id)
    dist = await bracket_service.distribution(session, ctx)
    scores = {
        s.match_id: s
        for s in (
            await session.execute(select(Score).where(Score.user_id == principal.user.id, Score.season_id == season.id))
        ).scalars()
    }
    out = []
    for m in ctx.matches:
        item = match_out(m, ctx.seeds, ctx.now).model_dump()
        item["my_pick"] = _pick_out(picks.get(m.id))
        item["my_points"] = scores[m.id].points if m.id in scores else None
        item["distribution"] = dist.get(m.id)
        out.append(item)
    return out


@router.get("/matches/{match_id}")
async def match_detail(match_id: int, principal: CurrentUser, session: DBSession) -> dict[str, Any]:
    match = await session.get(Match, match_id)
    if match is None:
        raise not_found("Spiel")
    season = await resolve_season(session, match.season_id)
    if season.status == SeasonStatus.DRAFT and not principal.is_admin:
        raise not_found("Spiel")
    ctx = await bracket_service.load_context(session, season)
    assert principal.user is not None
    revealed = is_locked(match, ctx.now)
    rows = (
        (
            await session.execute(
                select(User, Prediction)
                .join(Bracket, Bracket.user_id == User.id)
                .outerjoin(Prediction, (Prediction.bracket_id == Bracket.id) & (Prediction.match_id == match.id))
                .where(Bracket.season_id == season.id, User.is_bot.is_(False))
                .order_by(User.display_name)
            )
        )
        .unique()
        .all()
    )
    scores = {s.user_id: s for s in (await session.execute(select(Score).where(Score.match_id == match.id))).scalars()}
    picks = []
    for user, pred in rows:
        visible = revealed or user.id == principal.user.id or principal.is_admin
        s = scores.get(user.id)
        picks.append(
            {
                "user": {"id": user.id, "display_name": user.display_name, "avatar_url": user.avatar_url},
                "has_pick": pred is not None,
                "pick": _pick_out(pred) if visible else None,
                "hidden": not visible and pred is not None,
                "points": s.points if s else None,
                "exact_correct": s.exact_correct if s else None,
                "winner_correct": s.winner_correct if s else None,
            }
        )
    my_request = (
        (
            await session.execute(
                select(PredictionChange)
                .where(PredictionChange.user_id == principal.user.id, PredictionChange.match_id == match.id)
                .order_by(PredictionChange.created_at.desc())
                .limit(1)
            )
        )
        .unique()
        .scalar_one_or_none()
    )
    my_pick = next((p["pick"] for p in picks if p["user"]["id"] == principal.user.id), None)
    dist = await bracket_service.distribution(session, ctx)
    return {
        "match": match_out(match, ctx.seeds, ctx.now),
        "season": SeasonOut.model_validate(season),
        "revealed": revealed,
        "my_pick": my_pick,
        "my_change_request": None if my_request is None else change_request_out(my_request),
        "distribution": dist.get(match.id),
        "picks": picks,
    }


# ------------------------------------------------------------------ brackets


async def _owner(session, principal: Principal, user_id: str) -> User:
    if user_id == "me":
        assert principal.user is not None
        return principal.user
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise not_found("Benutzer")
    user = await session.get(User, uid)
    if user is None or user.is_bot:
        raise not_found("Benutzer")
    return user


@router.get("/seasons/{season_id}/bracket/{user_id}")
async def get_bracket(season_id: int, user_id: str, principal: CurrentUser, session: DBSession) -> dict[str, Any]:
    season = await resolve_season(session, season_id)
    owner = await _owner(session, principal, user_id)
    ctx = await bracket_service.load_context(session, season)
    return await bracket_service.bracket_view(session, ctx, owner, principal)


@router.put("/seasons/{season_id}/bracket/me/picks/{slot}", dependencies=[PickLimiter])
async def put_pick(
    season_id: int, slot: str, body: PickIn, principal: CurrentUser, session: DBSession
) -> dict[str, Any]:
    if slot not in SLOTS:
        raise not_found("Slot")
    season = await resolve_season(session, season_id)
    await bracket_service.set_pick(
        session, principal, season, slot, body.winner_team_id, body.winner_score, body.loser_score
    )
    ctx = await bracket_service.load_context(session, season)
    return await bracket_service.bracket_view(session, ctx, principal.user, principal)  # type: ignore[arg-type]


@router.delete("/seasons/{season_id}/bracket/me/picks/{slot}", dependencies=[PickLimiter])
async def delete_pick(season_id: int, slot: str, principal: CurrentUser, session: DBSession) -> dict[str, Any]:
    if slot not in SLOTS:
        raise not_found("Slot")
    season = await resolve_season(session, season_id)
    await bracket_service.clear_pick(session, principal, season, slot)
    ctx = await bracket_service.load_context(session, season)
    return await bracket_service.bracket_view(session, ctx, principal.user, principal)  # type: ignore[arg-type]


@router.post("/seasons/{season_id}/bracket/me/submit")
async def submit(season_id: int, principal: CurrentUser, session: DBSession) -> dict[str, Any]:
    season = await resolve_season(session, season_id)
    await bracket_service.submit_bracket(session, principal, season)
    ctx = await bracket_service.load_context(session, season)
    return await bracket_service.bracket_view(session, ctx, principal.user, principal)  # type: ignore[arg-type]


@router.get("/seasons/{season_id}/brackets")
async def all_brackets(season_id: int, principal: CurrentUser, session: DBSession) -> list[dict[str, Any]]:
    season = await resolve_season(session, season_id)
    ctx = await bracket_service.load_context(session, season)
    return await bracket_service.brackets_overview(session, ctx, principal)


@router.get("/seasons/{season_id}/compare")
async def compare_brackets(
    season_id: int, principal: CurrentUser, session: DBSession, a: str = Query(...), b: str = Query(...)
) -> dict[str, Any]:
    season = await resolve_season(session, season_id)
    ctx = await bracket_service.load_context(session, season)
    view_a = await bracket_service.bracket_view(session, ctx, await _owner(session, principal, a), principal)
    view_b = await bracket_service.bracket_view(session, ctx, await _owner(session, principal, b), principal)
    diff = []
    for sa, sb in zip(view_a["slots"], view_b["slots"], strict=True):
        pa, pb = sa["pick"], sb["pick"]
        if sa["pick_hidden"] or sb["pick_hidden"]:
            state = "hidden"
        elif pa is None or pb is None:
            state = "missing"
        elif pa["winner_team_id"] == pb["winner_team_id"]:
            state = "same"
        else:
            state = "different"
        diff.append({"slot": sa["slot"], "state": state})
    dist = await bracket_service.distribution(session, ctx)
    return {"a": view_a, "b": view_b, "diff": diff, "distribution": list(dist.values())}


@router.get("/seasons/{season_id}/distribution")
async def community_distribution(season_id: int, principal: CurrentUser, session: DBSession) -> list[dict[str, Any]]:
    season = await resolve_season(session, season_id)
    ctx = await bracket_service.load_context(session, season)
    return list((await bracket_service.distribution(session, ctx)).values())


# ------------------------------------------------------------------ leaderboard & dashboard


def _leader_out(lb: Leaderboard, me: uuid.UUID | None) -> dict[str, Any]:
    return {
        "rank": lb.rank,
        "previous_rank": lb.previous_rank,
        "user": {"id": lb.user_id, "display_name": lb.user.display_name, "avatar_url": lb.user.avatar_url},
        "points": lb.points,
        "correct_winners": lb.correct_winners,
        "wrong_picks": lb.wrong_picks,
        "missed_picks": lb.missed_picks,
        "exact_scores": lb.exact_scores,
        "champion_correct": lb.champion_correct,
        "scored_matches": lb.scored_matches,
        "is_me": lb.user_id == me,
    }


@router.get("/seasons/{season_id}/leaderboard")
async def leaderboard(season_id: int, principal: CurrentUser, session: DBSession) -> list[dict[str, Any]]:
    season = await resolve_season(session, season_id)
    return [_leader_out(lb, principal.user_id) for lb in await leaderboard_rows(session, season.id)]


@router.get("/dashboard")
async def dashboard(principal: CurrentUser, session: DBSession, season_id: int | None = None) -> dict[str, Any]:
    assert principal.user is not None
    season = await resolve_season(session, season_id) if season_id else await get_current_season(session)
    if season is None:
        return {"season": None}
    ctx = await bracket_service.load_context(session, season)
    now = now_utc()
    upcoming = sorted(
        [m for m in ctx.matches if m.teams_known and m.status in (MatchStatus.OPEN, MatchStatus.LOCKED)],
        key=lambda m: (m.kickoff_at is None, m.kickoff_at or now),
    )
    next_match = next((m for m in upcoming if m.kickoff_at and m.kickoff_at >= now), None) or (
        upcoming[0] if upcoming else None
    )
    recent = sorted(
        [m for m in ctx.matches if m.status == MatchStatus.FINAL],
        key=lambda m: m.finalized_at or now,
        reverse=True,
    )[:6]
    rows = await leaderboard_rows(session, season.id)
    mine = next((r for r in rows if r.user_id == principal.user.id), None)
    picks = await _my_picks(session, principal.user.id, season.id)
    bracket = await bracket_service.get_bracket(session, principal.user.id, season.id)
    resolved = ctx.resolve(bracket_service.picks_by_slot(bracket.predictions, ctx.by_id) if bracket else {})
    missing = bracket_service.missing_open_picks(ctx, resolved)
    pending_requests = 0
    if principal.is_admin:
        pending_requests = (
            await session.execute(
                select(func.count(PredictionChange.id)).where(PredictionChange.status == ChangeRequestStatus.PENDING)
            )
        ).scalar_one()
    total_final = len([m for m in ctx.matches if m.status == MatchStatus.FINAL])
    next_out = None
    if next_match is not None:
        next_out = match_out(next_match, ctx.seeds, now).model_dump()
        next_out["my_pick"] = _pick_out(picks.get(next_match.id))
    return {
        "season": SeasonOut.model_validate(season),
        "me": {
            "display_name": principal.user.display_name,
            "rank": mine.rank if mine else None,
            "participants": len(rows),
            "points": mine.points if mine else 0,
            "correct_winners": mine.correct_winners if mine else 0,
            "scored_matches": mine.scored_matches if mine else 0,
            "total_final_matches": total_final,
            "exact_scores": mine.exact_scores if mine else 0,
            "champion_correct": mine.champion_correct if mine else False,
            "missing_open_picks": len(missing),
            "submitted_at": bracket.submitted_at if bracket else None,
        },
        "next_match": next_out,
        "recent_results": [match_out(m, ctx.seeds, now) for m in recent],
        "leaderboard": [_leader_out(r, principal.user.id) for r in rows[:7]],
        "pending_change_requests": pending_requests,
    }


# ------------------------------------------------------------------ change requests (user side)


class ChangeRequestIn(BaseModel):
    winner_team_id: int
    winner_score: int | None = Field(default=None, ge=0, le=99)
    loser_score: int | None = Field(default=None, ge=0, le=99)
    reason: str | None = Field(default=None, max_length=500)


@router.post(
    "/matches/{match_id}/change-requests",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_rate_limit("change-request", 10, 60))],
)
async def create_change_request(match_id: int, body: ChangeRequestIn, principal: CurrentUser, session: DBSession):
    cr = await change_requests.create_request(
        session, principal, match_id, body.winner_team_id, body.winner_score, body.loser_score, body.reason
    )
    cr = (await session.execute(select(PredictionChange).where(PredictionChange.id == cr.id))).unique().scalar_one()
    return change_request_out(cr)


@router.get("/change-requests/me")
async def my_change_requests(principal: CurrentUser, session: DBSession) -> list[dict[str, Any]]:
    rows = await session.execute(
        select(PredictionChange)
        .where(PredictionChange.user_id == principal.user_id)
        .order_by(PredictionChange.created_at.desc())
        .limit(50)
    )
    return [change_request_out(cr) for cr in rows.unique().scalars()]


@router.delete("/change-requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_change_request(request_id: int, principal: CurrentUser, session: DBSession) -> None:
    await change_requests.cancel(session, principal, request_id)
