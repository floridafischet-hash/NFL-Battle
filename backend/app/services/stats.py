"""Statistics and Hall of Fame."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bracket, HallOfFame, Leaderboard, Match, Prediction, Score, Season, Team, User
from app.models.enums import Round, SeasonStatus
from app.services.bracket_engine import ROUND_LABELS, ROUND_ORDER
from app.services.scoring_rules import best_streak
from app.services.seasons import team_out


def _rate(correct: int, total: int) -> float:
    return round(100 * correct / total, 1) if total else 0.0


async def _ordered_scores(
    session: AsyncSession, user_id: uuid.UUID, season_id: int | None
) -> list[tuple[Score, Match]]:
    stmt = (
        select(Score, Match)
        .join(Match, Match.id == Score.match_id)
        .where(Score.user_id == user_id)
        .order_by(Match.finalized_at.asc().nulls_last(), Match.kickoff_at.asc().nulls_last(), Match.id)
    )
    if season_id is not None:
        stmt = stmt.where(Score.season_id == season_id)
    return [(s, m) for s, m in (await session.execute(stmt)).unique().all()]


def _summary(rows: list[tuple[Score, Match]]) -> dict[str, Any]:
    correct = sum(1 for s, _ in rows if s.winner_correct)
    wrong = sum(1 for s, _ in rows if s.has_pick and not s.winner_correct)
    missed = sum(1 for s, _ in rows if not s.has_pick)
    exact = sum(1 for s, _ in rows if s.exact_correct)
    best, current = best_streak([s.winner_correct for s, _ in rows])
    return {
        "points": sum(s.points for s, _ in rows),
        "correct_winners": correct,
        "wrong_picks": wrong,
        "missed_picks": missed,
        "exact_scores": exact,
        "scored_matches": len(rows),
        "hit_rate": _rate(correct, correct + wrong),
        "best_streak": best,
        "current_streak": current,
        "champion_correct": any(m.round == Round.SUPER_BOWL and s.winner_correct for s, m in rows),
    }


async def user_stats(session: AsyncSession, user_id: uuid.UUID, season_id: int | None) -> dict[str, Any]:
    user = await session.get(User, user_id)
    if user is None or user.is_bot:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Benutzer nicht gefunden")

    season_rows = await _ordered_scores(session, user_id, season_id) if season_id else []
    all_rows = await _ordered_scores(session, user_id, None)

    rounds = []
    for r in ROUND_ORDER:
        rr = [(s, m) for s, m in season_rows if m.round == r]
        c = sum(1 for s, _ in rr if s.winner_correct)
        rounds.append({"round": r.value, "label": ROUND_LABELS[r], "correct": c, "total": len(rr)})

    participants = dict(
        (await session.execute(select(Leaderboard.season_id, func.count()).group_by(Leaderboard.season_id))).all()
    )
    history = []
    lb_rows = (
        (
            await session.execute(
                select(Leaderboard, Season)
                .join(Season, Season.id == Leaderboard.season_id)
                .where(Leaderboard.user_id == user_id)
                .order_by(Season.year.desc())
            )
        )
        .unique()
        .all()
    )
    for lb, season in lb_rows:
        history.append(
            {
                "season_id": season.id,
                "season_name": season.name,
                "status": season.status.value,
                "rank": lb.rank,
                "participants": participants.get(season.id, 0),
                "points": lb.points,
                "correct_winners": lb.correct_winners,
                "exact_scores": lb.exact_scores,
                "champion_correct": lb.champion_correct,
            }
        )
    current_lb = next((h for h in history if h["season_id"] == season_id), None)
    totals = _summary(all_rows)
    totals["seasons_played"] = len(history)
    totals["titles"] = sum(1 for h in history if h["status"] == SeasonStatus.COMPLETED.value and h["rank"] == 1)
    totals["champion_hits"] = sum(1 for h in history if h["champion_correct"])
    return {
        "user": {"id": user.id, "display_name": user.display_name, "avatar_url": user.avatar_url},
        "season": {
            **_summary(season_rows),
            "rank": current_lb["rank"] if current_lb else None,
            "participants": current_lb["participants"] if current_lb else 0,
        }
        if season_id
        else None,
        "rounds": rounds,
        "history": history,
        "totals": totals,
    }


async def compare_users(session: AsyncSession, a: uuid.UUID, b: uuid.UUID, season_id: int) -> dict[str, Any]:
    stats_a = await user_stats(session, a, season_id)
    stats_b = await user_stats(session, b, season_id)
    rows_a = {s.match_id: s for s, _ in await _ordered_scores(session, a, season_id)}
    rows_b = {s.match_id: s for s, _ in await _ordered_scores(session, b, season_id)}
    wins_a = wins_b = draws = 0
    for match_id in rows_a.keys() & rows_b.keys():
        pa, pb = rows_a[match_id].points, rows_b[match_id].points
        if pa > pb:
            wins_a += 1
        elif pb > pa:
            wins_b += 1
        else:
            draws += 1
    # same picks on scored (hence revealed) matches
    picks = (
        await session.execute(
            select(Bracket.user_id, Prediction.match_id, Prediction.winner_team_id)
            .join(Prediction, Prediction.bracket_id == Bracket.id)
            .where(
                Bracket.season_id == season_id,
                Bracket.user_id.in_([a, b]),
                Prediction.match_id.in_(list(rows_a.keys() | rows_b.keys()) or [-1]),
            )
        )
    ).all()
    by_user: dict[uuid.UUID, dict[int, int]] = {}
    for uid, mid, tid in picks:
        by_user.setdefault(uid, {})[mid] = tid
    common = by_user.get(a, {}).keys() & by_user.get(b, {}).keys()
    same = sum(1 for m in common if by_user[a][m] == by_user[b][m])
    return {
        "a": stats_a,
        "b": stats_b,
        "head_to_head": {"a_better": wins_a, "b_better": wins_b, "equal": draws},
        "same_picks": same,
        "compared_picks": len(common),
        "agreement": _rate(same, len(common)),
    }


async def season_overview(session: AsyncSession, season_id: int) -> dict[str, Any]:
    lbs = list(
        (
            await session.execute(
                select(Leaderboard).where(Leaderboard.season_id == season_id).order_by(Leaderboard.rank)
            )
        )
        .unique()
        .scalars()
    )
    table = []
    for lb in lbs:
        rows = await _ordered_scores(session, lb.user_id, season_id)
        summary = _summary(rows)
        table.append(
            {
                "user": {"id": lb.user_id, "display_name": lb.user.display_name, "avatar_url": lb.user.avatar_url},
                "rank": lb.rank,
                **summary,
            }
        )
    total_picks = (
        await session.execute(
            select(func.count(Score.id)).where(Score.season_id == season_id, Score.has_pick.is_(True))
        )
    ).scalar_one()
    finals = (
        await session.execute(
            select(func.count(Match.id)).where(Match.season_id == season_id, Match.finalized_at.is_not(None))
        )
    ).scalar_one()
    return {"table": table, "matches_final": finals, "total_scored_picks": int(total_picks)}


async def hall_of_fame(session: AsyncSession) -> dict[str, Any]:
    entries = list(
        (await session.execute(select(HallOfFame).join(Season).order_by(Season.year.desc()))).unique().scalars()
    )
    teams = {t.id: t for t in (await session.execute(select(Team))).scalars()}
    seasons = []
    for h in entries:
        standings = [
            {
                **row,
                "sb_pick_team": team_out(teams.get(row.get("sb_pick_team_id"))) if row.get("sb_pick_team_id") else None,
            }
            for row in h.final_standings
        ]
        seasons.append(
            {
                "season_id": h.season_id,
                "season_name": h.season.name,
                "year": h.season.year,
                "winner_user_id": h.winner_user_id,
                "winner_display_name": h.winner_display_name,
                "winner_points": h.winner_points,
                "winner_correct_winners": h.winner_correct_winners,
                "winner_exact_scores": h.winner_exact_scores,
                "champion_team": team_out(h.champion_team),
                "winner_sb_pick_team": team_out(h.winner_sb_pick_team),
                "standings": standings,
            }
        )

    rows = (
        (
            await session.execute(
                select(Leaderboard, Season)
                .join(Season, Season.id == Leaderboard.season_id)
                .where(Season.status == SeasonStatus.COMPLETED)
            )
        )
        .unique()
        .all()
    )
    agg: dict[uuid.UUID, dict[str, Any]] = {}
    for lb, _season in rows:
        e = agg.setdefault(
            lb.user_id,
            {
                "user": {"id": lb.user_id, "display_name": lb.user.display_name, "avatar_url": lb.user.avatar_url},
                "seasons_played": 0,
                "titles": 0,
                "total_points": 0,
                "correct_winners": 0,
                "exact_scores": 0,
                "champion_hits": 0,
                "best_rank": None,
            },
        )
        e["seasons_played"] += 1
        e["titles"] += 1 if lb.rank == 1 else 0
        e["total_points"] += lb.points
        e["correct_winners"] += lb.correct_winners
        e["exact_scores"] += lb.exact_scores
        e["champion_hits"] += 1 if lb.champion_correct else 0
        e["best_rank"] = lb.rank if e["best_rank"] is None else min(e["best_rank"], lb.rank)
    all_time = sorted(agg.values(), key=lambda e: (-e["titles"], -e["total_points"], e["user"]["display_name"].lower()))
    for i, e in enumerate(all_time, start=1):
        e["rank"] = i
        e["avg_points"] = round(e["total_points"] / e["seasons_played"], 1) if e["seasons_played"] else 0
    return {"seasons": seasons, "all_time": all_time}
