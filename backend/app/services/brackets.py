"""User brackets: picks, cascade, submission, visibility (anti-copy) and view building."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.models import Bracket, Leaderboard, Match, Prediction, PredictionChange, Score, Season, SeasonTeam, User
from app.models.enums import ChangeRequestStatus, MatchStatus, SeasonStatus
from app.realtime.events import publish
from app.services.audit import audit
from app.services.bracket_engine import (
    ROUND_LABELS,
    Pick,
    ResolvedSlot,
    picks_to_clear_after_change,
    resolve_bracket,
)
from app.services.seasons import (
    is_locked,
    load_matches,
    load_season_teams,
    match_states,
    not_found,
    now_utc,
    seed_map,
    team_out,
    team_seeds,
)


@dataclass
class SeasonContext:
    season: Season
    matches: list[Match]
    season_teams: list[SeasonTeam]
    now: datetime

    @property
    def by_slot(self) -> dict[str, Match]:
        return {m.slot: m for m in self.matches}

    @property
    def by_id(self) -> dict[int, Match]:
        return {m.id: m for m in self.matches}

    @property
    def seeds(self) -> dict[int, int]:
        return seed_map(self.season_teams)

    @property
    def states(self):
        return match_states(self.matches, self.now)

    def locked(self, slot: str) -> bool:
        match = self.by_slot.get(slot)
        return match is None or is_locked(match, self.now)

    def resolve(self, picks: dict[str, Pick]) -> dict[str, ResolvedSlot]:
        return resolve_bracket(team_seeds(self.season_teams), self.states, picks)


async def load_context(session: AsyncSession, season: Season) -> SeasonContext:
    return SeasonContext(
        season=season,
        matches=await load_matches(session, season.id),
        season_teams=await load_season_teams(session, season.id),
        now=now_utc(),
    )


async def get_bracket(
    session: AsyncSession, user_id: uuid.UUID, season_id: int, for_update: bool = False
) -> Bracket | None:
    stmt = select(Bracket).where(Bracket.user_id == user_id, Bracket.season_id == season_id)
    if for_update:
        stmt = stmt.with_for_update(of=Bracket)
    return (await session.execute(stmt)).unique().scalar_one_or_none()


async def get_or_create_bracket(
    session: AsyncSession, user_id: uuid.UUID, season_id: int, for_update: bool = False
) -> Bracket:
    bracket = await get_bracket(session, user_id, season_id, for_update)
    if bracket is None:
        await session.execute(
            insert(Bracket)
            .values(user_id=user_id, season_id=season_id)
            .on_conflict_do_nothing(constraint="uq_brackets_user_season")
        )
        bracket = await get_bracket(session, user_id, season_id, for_update)
        assert bracket is not None
    return bracket


def picks_by_slot(predictions: list[Prediction], by_id: dict[int, Match]) -> dict[str, Pick]:
    picks: dict[str, Pick] = {}
    for p in predictions:
        match = by_id.get(p.match_id)
        if match is not None:
            picks[match.slot] = Pick(p.winner_team_id, p.winner_score, p.loser_score)
    return picks


def pick_dict(p: Prediction | None) -> dict[str, Any] | None:
    if p is None:
        return None
    return {"winner_team_id": p.winner_team_id, "winner_score": p.winner_score, "loser_score": p.loser_score}


def missing_open_picks(ctx: SeasonContext, resolved: dict[str, ResolvedSlot]) -> list[str]:
    return [s for s, r in resolved.items() if not ctx.locked(s) and r.pick_state != "valid"]


def ensure_season_playable(season: Season) -> None:
    if season.status == SeasonStatus.COMPLETED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Die Saison ist abgeschlossen.")


async def set_pick(
    session: AsyncSession,
    principal: Principal,
    season: Season,
    slot: str,
    winner_team_id: int,
    winner_score: int | None,
    loser_score: int | None,
) -> None:
    ensure_season_playable(season)
    assert principal.user is not None
    ctx = await load_context(session, season)
    match = ctx.by_slot.get(slot)
    if match is None:
        raise not_found("Spiel")
    if ctx.locked(slot):
        raise HTTPException(status.HTTP_409_CONFLICT, "Dieses Spiel ist gesperrt. Bitte stelle einen Änderungsantrag.")

    bracket = await get_or_create_bracket(session, principal.user.id, season.id, for_update=True)
    picks = picks_by_slot(bracket.predictions, ctx.by_id)
    resolved = ctx.resolve(picks)
    r = resolved[slot]
    if not r.teams_known:
        raise HTTPException(status.HTTP_409_CONFLICT, "Die Paarung steht noch nicht fest – tippe zuerst die Vorrunde.")
    if winner_team_id not in (r.home_team_id, r.away_team_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Dieses Team spielt nicht in dieser Partie.")

    if not season.score_tips_enabled:
        winner_score = loser_score = None
    elif (winner_score is None) != (loser_score is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Bitte beide Punktzahlen angeben.")
    elif winner_score is not None and loser_score is not None and winner_score <= loser_score:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Der getippte Sieger muss mehr Punkte haben (kein Unentschieden in den Playoffs).",
        )

    existing = next((p for p in bracket.predictions if p.match_id == match.id), None)
    old = pick_dict(existing)
    if existing is None:
        existing = Prediction(
            bracket_id=bracket.id,
            match_id=match.id,
            winner_team_id=winner_team_id,
            winner_score=winner_score,
            loser_score=loser_score,
            updated_via="WEB",
        )
        bracket.predictions.append(existing)
    else:
        existing.winner_team_id = winner_team_id
        existing.winner_score = winner_score
        existing.loser_score = loser_score
        existing.updated_via = "WEB"
    new = pick_dict(existing)
    if old != new:
        audit(
            session,
            principal,
            "PREDICTION_UPDATED" if old else "PREDICTION_CREATED",
            "prediction",
            f"{principal.user.id}:{match.id}",
            old,
            {**(new or {}), "slot": slot},
            source="WEB",
        )

    picks[slot] = Pick(winner_team_id, winner_score, loser_score)
    await _apply_cascade(session, principal, ctx, bracket, picks)
    await session.flush()
    await publish(session, "bracket_updated", season_id=season.id, user_id=str(principal.user.id))
    await session.commit()


async def clear_pick(session: AsyncSession, principal: Principal, season: Season, slot: str) -> None:
    ensure_season_playable(season)
    assert principal.user is not None
    ctx = await load_context(session, season)
    match = ctx.by_slot.get(slot)
    if match is None:
        raise not_found("Spiel")
    if ctx.locked(slot):
        raise HTTPException(status.HTTP_409_CONFLICT, "Dieses Spiel ist gesperrt.")
    bracket = await get_or_create_bracket(session, principal.user.id, season.id, for_update=True)
    existing = next((p for p in bracket.predictions if p.match_id == match.id), None)
    if existing is None:
        return
    audit(
        session,
        principal,
        "PREDICTION_DELETED",
        "prediction",
        f"{principal.user.id}:{match.id}",
        pick_dict(existing),
        None,
    )
    bracket.predictions.remove(existing)
    picks = picks_by_slot(bracket.predictions, ctx.by_id)
    await _apply_cascade(session, principal, ctx, bracket, picks, force_unsubmit=True)
    await publish(session, "bracket_updated", season_id=season.id, user_id=str(principal.user.id))
    await session.commit()


async def _apply_cascade(
    session: AsyncSession,
    principal: Principal | None,
    ctx: SeasonContext,
    bracket: Bracket,
    picks: dict[str, Pick],
    force_unsubmit: bool = False,
) -> list[str]:
    """Remove open downstream picks that became invalid; un-submit an incomplete bracket."""
    resolved = ctx.resolve(picks)
    cleared = picks_to_clear_after_change(resolved)
    for slot in cleared:
        match = ctx.by_slot[slot]
        pred = next((p for p in bracket.predictions if p.match_id == match.id), None)
        if pred is not None:
            audit(
                session,
                principal,
                "PREDICTION_CLEARED",
                "prediction",
                f"{bracket.user_id}:{match.id}",
                pick_dict(pred),
                None,
                source="CASCADE",
            )
            bracket.predictions.remove(pred)
        picks.pop(slot, None)
    if cleared:
        resolved = ctx.resolve(picks)
    if bracket.submitted_at is not None and (force_unsubmit or cleared) and missing_open_picks(ctx, resolved):
        bracket.submitted_at = None
    return cleared


async def submit_bracket(session: AsyncSession, principal: Principal, season: Season) -> datetime:
    ensure_season_playable(season)
    assert principal.user is not None
    ctx = await load_context(session, season)
    bracket = await get_or_create_bracket(session, principal.user.id, season.id, for_update=True)
    resolved = ctx.resolve(picks_by_slot(bracket.predictions, ctx.by_id))
    missing = missing_open_picks(ctx, resolved)
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Es fehlen noch {len(missing)} gültige Tipps, bevor du dein Bracket abgeben kannst.",
        )
    bracket.submitted_at = ctx.now
    audit(
        session,
        principal,
        "BRACKET_SUBMITTED",
        "bracket",
        bracket.id,
        None,
        {"season_id": season.id, "picks": len(bracket.predictions)},
    )
    await publish(session, "bracket_updated", season_id=season.id, user_id=str(principal.user.id))
    await session.commit()
    return ctx.now


# --------------------------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------------------------


def can_see_all(viewer: Principal, owner_id: uuid.UUID) -> bool:
    return viewer.is_admin or viewer.user_id == owner_id


async def _scores_for(session: AsyncSession, user_id: uuid.UUID, season_id: int) -> dict[int, Score]:
    rows = await session.execute(select(Score).where(Score.user_id == user_id, Score.season_id == season_id))
    return {s.match_id: s for s in rows.scalars()}


async def _pending_requests(
    session: AsyncSession, user_id: uuid.UUID, match_ids: list[int]
) -> dict[int, PredictionChange]:
    rows = await session.execute(
        select(PredictionChange).where(
            PredictionChange.user_id == user_id,
            PredictionChange.match_id.in_(match_ids),
            PredictionChange.status == ChangeRequestStatus.PENDING,
        )
    )
    return {c.match_id: c for c in rows.unique().scalars()}


async def bracket_view(session: AsyncSession, ctx: SeasonContext, owner: User, viewer: Principal) -> dict[str, Any]:
    bracket = await get_bracket(session, owner.id, ctx.season.id)
    predictions = bracket.predictions if bracket else []
    all_picks = picks_by_slot(predictions, ctx.by_id)
    full = can_see_all(viewer, owner.id)
    visible = all_picks if full else {s: p for s, p in all_picks.items() if ctx.locked(s)}
    resolved = ctx.resolve(visible)
    seeds = ctx.seeds
    scores = await _scores_for(session, owner.id, ctx.season.id)
    pending = (
        await _pending_requests(session, owner.id, [m.id for m in ctx.matches]) if viewer.user_id == owner.id else {}
    )
    teams_by_id = _teams_index(ctx)

    slots_out = []
    for match in ctx.matches:
        r = resolved[match.slot]
        score = scores.get(match.id)
        cr = pending.get(match.id)
        hidden = match.slot in all_picks and match.slot not in visible
        slots_out.append(
            {
                "slot": match.slot,
                "match_id": match.id,
                "round": match.round,
                "round_label": ROUND_LABELS[match.round],
                "conference": match.conference,
                "home": team_out(teams_by_id.get(r.home_team_id), seeds),
                "away": team_out(teams_by_id.get(r.away_team_id), seeds),
                "teams_source": r.teams_source,
                "home_origin": r.home_origin,
                "away_origin": r.away_origin,
                "status": match.status,
                "locked": r.locked,
                "kickoff_at": match.kickoff_at,
                "lock_at": match.lock_at,
                "venue": match.venue,
                "home_score": match.home_score,
                "away_score": match.away_score,
                "winner_team_id": match.winner_team_id,
                "has_pick": match.slot in all_picks,
                "pick_hidden": hidden,
                "pick": None
                if r.pick is None
                else {
                    "winner_team_id": r.pick.winner_team_id,
                    "winner_score": r.pick.winner_score,
                    "loser_score": r.pick.loser_score,
                },
                "pick_state": "hidden" if hidden else r.pick_state,
                "effective_winner_team_id": r.effective_winner_team_id,
                "points": score.points if score else None,
                "winner_correct": score.winner_correct if score else None,
                "exact_correct": score.exact_correct if score else None,
                "pending_change_request": None
                if cr is None
                else {
                    "id": cr.id,
                    "new_winner_team_id": cr.new_winner_team_id,
                    "new_winner_score": cr.new_winner_score,
                    "new_loser_score": cr.new_loser_score,
                    "created_at": cr.created_at,
                },
            }
        )

    byes = {}
    for st in ctx.season_teams:
        if st.seed == 1:
            byes[st.conference.value] = team_out(st.team, seeds)
    leader = await session.get(Leaderboard, (ctx.season.id, owner.id))
    sb = resolved.get("SB")
    return {
        "season_id": ctx.season.id,
        "user": {
            "id": owner.id,
            "display_name": owner.display_name,
            "avatar_url": owner.avatar_url,
            "username": owner.username,
        },
        "is_owner": viewer.user_id == owner.id,
        "full_visibility": full,
        "submitted_at": bracket.submitted_at if bracket else None,
        "picks_count": len(all_picks),
        "missing_open_picks": len(missing_open_picks(ctx, ctx.resolve(all_picks))) if full else None,
        "champion_team_id": (
            sb.pick.winner_team_id if sb and sb.pick and sb.pick_state in ("valid", "pending") else None
        ),
        "byes": byes,
        "slots": slots_out,
        "points": leader.points if leader else 0,
        "rank": leader.rank if leader else None,
        "score_tips_enabled": ctx.season.score_tips_enabled,
    }


def _teams_index(ctx: SeasonContext) -> dict[int, Any]:
    teams: dict[int, Any] = {}
    for st in ctx.season_teams:
        teams[st.team_id] = st.team
    for m in ctx.matches:
        for t in (m.home_team, m.away_team, m.winner_team):
            if t is not None:
                teams[t.id] = t
    return teams


async def brackets_overview(session: AsyncSession, ctx: SeasonContext, viewer: Principal) -> list[dict[str, Any]]:
    users = list(
        (await session.execute(select(User).where(User.is_bot.is_(False), User.is_active.is_(True)))).scalars()
    )
    brackets = {
        b.user_id: b
        for b in (await session.execute(select(Bracket).where(Bracket.season_id == ctx.season.id))).unique().scalars()
    }
    leaders = {
        lb.user_id: lb
        for lb in (await session.execute(select(Leaderboard).where(Leaderboard.season_id == ctx.season.id)))
        .unique()
        .scalars()
    }
    teams = _teams_index(ctx)
    sb_locked = ctx.locked("SB")
    out = []
    for u in users:
        b = brackets.get(u.id)
        picks = picks_by_slot(b.predictions, ctx.by_id) if b else {}
        if b is None and ctx.season.status == SeasonStatus.COMPLETED:
            continue
        resolved = ctx.resolve(picks)
        missing = missing_open_picks(ctx, resolved)
        champion = None
        sb_slot = resolved["SB"]
        if (sb_locked or can_see_all(viewer, u.id)) and sb_slot.pick and sb_slot.pick_state in ("valid", "pending"):
            champion = team_out(teams.get(sb_slot.pick.winner_team_id), ctx.seeds)
        lb = leaders.get(u.id)
        out.append(
            {
                "user": {
                    "id": u.id,
                    "display_name": u.display_name,
                    "avatar_url": u.avatar_url,
                    "username": u.username,
                },
                "is_me": u.id == viewer.user_id,
                "picks_count": len(picks),
                "missing_open_picks": len(missing),
                "submitted_at": b.submitted_at if b else None,
                "champion": champion,
                "points": lb.points if lb else 0,
                "rank": lb.rank if lb else None,
            }
        )
    out.sort(key=lambda e: (e["rank"] or 999, e["user"]["display_name"].lower()))
    return out


async def distribution(session: AsyncSession, ctx: SeasonContext) -> dict[int, dict[str, Any]]:
    """Community pick distribution, only for matches that are already locked (anti-copy)."""
    revealed = [m for m in ctx.matches if is_locked(m, ctx.now)]
    if not revealed:
        return {}
    rows = await session.execute(
        select(Prediction.match_id, Prediction.winner_team_id)
        .join(Bracket, Bracket.id == Prediction.bracket_id)
        .join(User, User.id == Bracket.user_id)
        .where(Prediction.match_id.in_([m.id for m in revealed]), User.is_bot.is_(False))
    )
    counts: dict[int, dict[int, int]] = {}
    for match_id, team_id in rows:
        counts.setdefault(match_id, {}).setdefault(team_id, 0)
        counts[match_id][team_id] += 1
    result = {}
    for m in revealed:
        c = counts.get(m.id, {})
        total = sum(c.values())
        entries = [
            {"team_id": tid, "count": n, "percent": round(100 * n / total) if total else 0}
            for tid, n in sorted(c.items(), key=lambda kv: -kv[1])
        ]
        result[m.id] = {"match_id": m.id, "slot": m.slot, "total": total, "teams": entries}
    return result


def match_status_is_scorable(match: Match) -> bool:
    return match.status == MatchStatus.FINAL and match.winner_team_id is not None
