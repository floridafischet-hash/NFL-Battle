"""Database side of the scoring: per-match scores, leaderboard, full recalculation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Integer, case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.models import Bracket, Leaderboard, Match, Prediction, Score, Season, User
from app.models.enums import MatchStatus, Round
from app.realtime.events import publish
from app.services.audit import audit
from app.services.bracket_engine import Pick
from app.services.scoring_rules import (
    ActualResult,
    PickScore,
    ScoringConfig,
    StandingInput,
    competition_ranks,
    score_pick,
)


def scoring_config(season: Season) -> ScoringConfig:
    return ScoringConfig(
        winner_points=season.winner_points,
        exact_score_points=season.exact_score_points,
        champion_bonus=season.champion_bonus,
        score_tips_enabled=season.score_tips_enabled,
    )


def actual_result(match: Match) -> ActualResult | None:
    if match.status != MatchStatus.FINAL or match.winner_team_id is None:
        return None
    assert match.home_score is not None and match.away_score is not None
    hi, lo = max(match.home_score, match.away_score), min(match.home_score, match.away_score)
    return ActualResult(match.winner_team_id, hi, lo, match.round == Round.SUPER_BOWL)


async def score_match(session: AsyncSession, season: Season, match: Match) -> list[tuple[User, PickScore]]:
    """(Re)calculate the scores of one match. Idempotent: old rows are replaced.

    The unique constraint (user_id, match_id) guarantees that points can never be awarded twice.
    """
    await session.execute(delete(Score).where(Score.match_id == match.id))
    result = actual_result(match)
    if result is None:
        return []
    config = scoring_config(season)
    brackets = list(
        (
            await session.execute(
                select(Bracket).join(User, User.id == Bracket.user_id).where(
                    Bracket.season_id == season.id, User.is_bot.is_(False)
                )
            )
        )
        .unique()
        .scalars()
    )
    predictions = {
        p.bracket_id: p
        for p in (await session.execute(select(Prediction).where(Prediction.match_id == match.id))).unique().scalars()
    }
    out: list[tuple[User, PickScore]] = []
    for bracket in brackets:
        pred = predictions.get(bracket.id)
        pick = Pick(pred.winner_team_id, pred.winner_score, pred.loser_score) if pred else None
        ps = score_pick(pick, result, config)
        session.add(
            Score(
                user_id=bracket.user_id,
                match_id=match.id,
                season_id=season.id,
                prediction_id=pred.id if pred else None,
                winner_correct=ps.winner_correct,
                exact_correct=ps.exact_correct,
                has_pick=ps.has_pick,
                base_points=ps.base_points,
                bonus_points=ps.bonus_points,
                points=ps.points,
            )
        )
        out.append((bracket.user, ps))
    await session.flush()
    out.sort(key=lambda t: (-t[1].points, t[0].display_name.lower()))
    return out


async def recompute_leaderboard(session: AsyncSession, season: Season) -> list[Leaderboard]:
    s = Score
    agg = (
        select(
            Bracket.user_id,
            User.display_name,
            func.coalesce(func.sum(s.points), 0).label("points"),
            func.coalesce(func.sum(case((s.winner_correct, 1), else_=0)), 0).label("correct"),
            func.coalesce(func.sum(case(((s.has_pick & ~s.winner_correct), 1), else_=0)), 0).label("wrong"),
            func.coalesce(func.sum(case((~s.has_pick, 1), else_=0)), 0).label("missed"),
            func.coalesce(func.sum(case((s.exact_correct, 1), else_=0)), 0).label("exact"),
            func.coalesce(
                func.max(case(((Match.slot == "SB") & s.winner_correct, 1), else_=0)), 0
            ).cast(Integer).label("champion"),
            func.count(s.id).label("scored"),
        )
        .select_from(Bracket)
        .join(User, User.id == Bracket.user_id)
        .outerjoin(s, (s.user_id == Bracket.user_id) & (s.season_id == Bracket.season_id))
        .outerjoin(Match, Match.id == s.match_id)
        .where(Bracket.season_id == season.id, User.is_bot.is_(False))
        .group_by(Bracket.user_id, User.display_name)
    )
    rows = (await session.execute(agg)).all()
    inputs = [StandingInput(r.user_id, int(r.points), int(r.exact), int(r.correct), r.display_name) for r in rows]
    by_user = {r.user_id: r for r in rows}
    existing = {
        lb.user_id: lb
        for lb in (await session.execute(select(Leaderboard).where(Leaderboard.season_id == season.id))).unique().scalars()
    }
    result: list[Leaderboard] = []
    for entry, rank in competition_ranks(inputs):
        r = by_user[entry.key]
        lb = existing.pop(entry.key, None)
        if lb is None:
            lb = Leaderboard(season_id=season.id, user_id=entry.key, rank=rank, previous_rank=None)
            session.add(lb)
        elif lb.rank != rank:
            lb.previous_rank = lb.rank
            lb.rank = rank
        lb.points = int(r.points)
        lb.correct_winners = int(r.correct)
        lb.wrong_picks = int(r.wrong)
        lb.missed_picks = int(r.missed)
        lb.exact_scores = int(r.exact)
        lb.champion_correct = bool(r.champion)
        lb.scored_matches = int(r.scored)
        result.append(lb)
    for stale in existing.values():
        await session.delete(stale)
    await session.flush()
    await publish(session, "leaderboard_updated", season_id=season.id)
    return result


async def leaderboard_rows(session: AsyncSession, season_id: int) -> list[Leaderboard]:
    rows = await session.execute(
        select(Leaderboard)
        .join(User, User.id == Leaderboard.user_id)
        .where(Leaderboard.season_id == season_id)
        .order_by(Leaderboard.rank, User.display_name)
    )
    return list(rows.unique().scalars())


async def leaderboard_top(session: AsyncSession, season_id: int, limit: int = 5) -> list[dict[str, Any]]:
    rows = await leaderboard_rows(session, season_id)
    return [
        {"rank": r.rank, "user_id": str(r.user_id), "display_name": r.user.display_name, "points": r.points}
        for r in rows[:limit]
    ]


async def recalculate_season(session: AsyncSession, season: Season, principal: Principal | None) -> dict[str, int]:
    """Recalculate all scores of a season from scratch (e.g. after changing the point values)."""
    matches = list(
        (await session.execute(select(Match).where(Match.season_id == season.id).with_for_update(of=Match)))
        .unique()
        .scalars()
    )
    before = (
        await session.execute(select(func.coalesce(func.sum(Score.points), 0)).where(Score.season_id == season.id))
    ).scalar_one()
    scored = 0
    for match in matches:
        rows = await score_match(session, season, match)
        if rows:
            scored += 1
    await recompute_leaderboard(session, season)
    after = (
        await session.execute(select(func.coalesce(func.sum(Score.points), 0)).where(Score.season_id == season.id))
    ).scalar_one()
    audit(
        session,
        principal,
        "SCORES_RECALCULATED",
        "season",
        season.id,
        {"total_points": int(before)},
        {"total_points": int(after), "matches_scored": scored},
        source="ADMIN" if principal else "SYSTEM",
    )
    return {"matches_scored": scored, "total_points_before": int(before), "total_points_after": int(after)}
