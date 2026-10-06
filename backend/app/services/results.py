"""Applying match results (admin or agent), round advancement and season completion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.models import Bracket, HallOfFame, Match, Prediction, Score, Season
from app.models.enums import MatchStatus, ResultSource, Round, SeasonStatus, SystemMessageType
from app.realtime.events import publish
from app.services import bot
from app.services.audit import audit
from app.services.bracket_engine import ROUND_LABELS, actual_advancements, downstream_slots
from app.services.notifications import notify_all
from app.services.scoring import leaderboard_rows, leaderboard_top, recompute_leaderboard, score_match
from app.services.seasons import (
    is_locked,
    load_matches,
    load_season_teams,
    match_label,
    match_states,
    now_utc,
    team_seeds,
)

MAX_SCORE = 99


def match_snapshot(match: Match) -> dict[str, Any]:
    return {
        "status": match.status.value,
        "home_team_id": match.home_team_id,
        "away_team_id": match.away_team_id,
        "home_score": match.home_score,
        "away_score": match.away_score,
        "winner_team_id": match.winner_team_id,
        "kickoff_at": match.kickoff_at.isoformat() if match.kickoff_at else None,
        "lock_at": match.lock_at.isoformat() if match.lock_at else None,
    }


def conflict(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail)


def validate_scores(match: Match, home_score: int, away_score: int) -> int:
    """Return the winner team id or raise 422."""
    if not match.teams_known:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Für dieses Spiel stehen noch keine Teams fest.")
    for value in (home_score, away_score):
        if not isinstance(value, int) or value < 0 or value > MAX_SCORE:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unplausibler Spielstand.")
    if home_score == away_score:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Playoff-Spiele enden nicht unentschieden.")
    assert match.home_team_id is not None and match.away_team_id is not None
    return match.home_team_id if home_score > away_score else match.away_team_id


async def lock_match(session: AsyncSession, match_id: int) -> Match:
    match = (
        (await session.execute(select(Match).where(Match.id == match_id).with_for_update(of=Match)))
        .unique()
        .scalar_one_or_none()
    )
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Spiel nicht gefunden")
    await session.refresh(match)
    return match


async def lock_season(session: AsyncSession, season_id: int) -> Season:
    season = (
        (await session.execute(select(Season).where(Season.id == season_id).with_for_update(of=Season)))
        .unique()
        .scalar_one()
    )
    return season


@dataclass
class ResultOutcome:
    match: Match
    correction: bool
    advanced: list[Match] = field(default_factory=list)
    season_completed: bool = False
    points: list[dict[str, Any]] = field(default_factory=list)


async def apply_result(
    session: AsyncSession,
    match_id: int,
    home_score: int,
    away_score: int,
    principal: Principal | None,
    source: ResultSource,
    note: dict[str, Any] | None = None,
) -> ResultOutcome:
    """Store a final result and run the whole pipeline. Caller commits."""
    match = await lock_match(session, match_id)
    season = await lock_season(session, match.season_id)
    if match.status == MatchStatus.VOID:
        raise conflict("Das Spiel ist annulliert (VOID). Bitte zuerst wieder öffnen.")
    winner = validate_scores(match, home_score, away_score)

    correction = match.status == MatchStatus.FINAL
    if correction and (match.home_score, match.away_score) == (home_score, away_score):
        return ResultOutcome(match=match, correction=False)

    matches = await load_matches(session, season.id)
    by_slot = {m.slot: m for m in matches}
    if correction and winner != match.winner_team_id:
        for slot in downstream_slots(match.slot):
            dm = by_slot.get(slot)
            if dm is not None and dm.teams_known and (dm.status == MatchStatus.FINAL or is_locked(dm)):
                raise conflict(
                    f"Der Sieger ändert sich, aber das Folgespiel {slot} ist bereits gesperrt/gewertet. "
                    "Bitte zuerst dessen Ergebnis zurücksetzen bzw. Paarung korrigieren."
                )

    old = match_snapshot(match)
    match.home_score = home_score
    match.away_score = away_score
    match.winner_team_id = winner
    match.status = MatchStatus.FINAL
    match.result_source = source
    match.finalized_at = now_utc()
    match.result_check_requested_at = None
    match.result_set_by = principal.user_id if principal else None
    await session.flush()
    await session.refresh(match, ["winner_team"])

    action = "MATCH_RESULT_CORRECTED" if correction else "MATCH_RESULT_SET"
    audit(
        session,
        principal,
        action,
        "match",
        match.id,
        old,
        {**match_snapshot(match), **(note or {})},
        source=source.value,
    )

    outcome = ResultOutcome(match=match, correction=correction)
    await _after_result_change(session, season, match, principal, outcome)
    return outcome


async def _after_result_change(
    session: AsyncSession, season: Season, match: Match, principal: Principal | None, outcome: ResultOutcome
) -> None:
    scored = await score_match(session, season, match)
    await recompute_leaderboard(session, season)
    outcome.points = [
        {
            "user_id": str(user.id),
            "display_name": user.display_name,
            "points": ps.points,
            "winner_correct": ps.winner_correct,
            "exact_correct": ps.exact_correct,
            "has_pick": ps.has_pick,
            "icon": bot.pick_icon(ps.has_pick, ps.winner_correct, ps.exact_correct),
        }
        for user, ps in scored
    ]
    top = await leaderboard_top(session, season.id, 5)
    text = bot.final_text(match, outcome.points, top, outcome.correction)
    version = match.finalized_at.isoformat() if match.finalized_at else ""
    await bot.post(
        session,
        SystemMessageType.CORRECTION if outcome.correction else SystemMessageType.FINAL,
        text,
        {"match": bot.match_payload(match), "points": outcome.points, "leaderboard": top},
        season_id=season.id,
        match_id=match.id,
        dedupe_key=f"FINAL:{match.id}:{match.home_score}:{match.away_score}:{version}",
    )
    outcome.advanced = await advance_rounds(session, season, principal)
    if match.round == Round.SUPER_BOWL:
        await complete_season(session, season, match, principal)
        outcome.season_completed = True
    await publish(session, "match_updated", season_id=season.id, match_id=match.id)


async def advance_rounds(session: AsyncSession, season: Season, principal: Principal | None) -> list[Match]:
    """Fill next-round pairings that follow from FINAL results (NFL reseeding)."""
    matches = await load_matches(session, season.id)
    season_teams = await load_season_teams(session, season.id)
    by_slot = {m.slot: m for m in matches}
    targets = actual_advancements(team_seeds(season_teams), match_states(matches))
    changed: list[Match] = []
    for slot, (home, away) in targets.items():
        m = by_slot[slot]
        if (m.home_team_id, m.away_team_id) == (home, away) or is_locked(m):
            continue
        old = match_snapshot(m)
        m.home_team_id, m.away_team_id = home, away
        await session.flush()
        await session.refresh(m, ["home_team", "away_team"])
        audit(session, principal, "MATCH_TEAMS_ASSIGNED", "match", m.id, old, match_snapshot(m), source="SYSTEM")
        changed.append(m)
    if changed:
        await announce_matchups(session, season, changed, SystemMessageType.NEXT_ROUND)
        await notify_all(
            session,
            "NEXT_ROUND",
            "Neue Paarungen – jetzt tippen!",
            ", ".join(match_label(m) for m in changed),
            "/bracket",
        )
    return changed


async def announce_matchups(
    session: AsyncSession, season: Season, matches: list[Match], type_: SystemMessageType
) -> None:
    matches = [m for m in matches if m.teams_known]
    if not matches:
        return
    rounds = sorted({ROUND_LABELS[m.round] for m in matches})
    header = "NÄCHSTE RUNDE" if type_ == SystemMessageType.NEXT_ROUND else "NEUE PAARUNGEN"
    lines = [f"{header}: {', '.join(rounds)}"]
    for m in matches:
        lines.append(f"{m.home_team.short_name} vs {m.away_team.short_name} – {bot.local_time(m.kickoff_at)}")
    lines.append("Jetzt tippen! 🏈")
    key = ";".join(f"{m.slot}={m.home_team_id}-{m.away_team_id}" for m in matches)
    await bot.post(
        session,
        type_,
        "\n".join(lines),
        {"matches": [bot.match_payload(m) for m in matches], "rounds": rounds},
        season_id=season.id,
        dedupe_key=f"{type_.value}:{season.id}:{key}"[:120],
    )


async def complete_season(session: AsyncSession, season: Season, sb: Match, principal: Principal | None) -> HallOfFame:
    """Super Bowl is final: freeze standings into the Hall of Fame."""
    season.status = SeasonStatus.COMPLETED
    season.champion_team_id = sb.winner_team_id
    season.completed_at = now_utc()
    rows = await leaderboard_rows(session, season.id)
    sb_picks = {
        b_user: team_id
        for b_user, team_id in (
            await session.execute(
                select(Bracket.user_id, Prediction.winner_team_id)
                .join(Prediction, Prediction.bracket_id == Bracket.id)
                .where(Prediction.match_id == sb.id)
            )
        ).all()
    }
    standings = [
        {
            "rank": r.rank,
            "user_id": str(r.user_id),
            "display_name": r.user.display_name,
            "points": r.points,
            "correct_winners": r.correct_winners,
            "exact_scores": r.exact_scores,
            "champion_correct": r.champion_correct,
            "sb_pick_team_id": sb_picks.get(r.user_id),
        }
        for r in rows
    ]
    winners = [r for r in rows if r.rank == 1]
    hof = await session.get(HallOfFame, season.id)
    if hof is None:
        hof = HallOfFame(season_id=season.id)
        session.add(hof)
    first = winners[0] if winners else None
    hof.winner_user_id = first.user_id if first else None
    hof.winner_display_name = " & ".join(w.user.display_name for w in winners) if winners else "—"
    hof.winner_points = first.points if first else 0
    hof.winner_correct_winners = first.correct_winners if first else 0
    hof.winner_exact_scores = first.exact_scores if first else 0
    hof.champion_team_id = sb.winner_team_id
    hof.winner_sb_pick_team_id = sb_picks.get(first.user_id) if first else None
    hof.final_standings = standings
    await session.flush()

    champion = sb.winner_team.short_name if sb.winner_team else "?"
    text = (
        f"🏆 SUPER BOWL CHAMPION: {champion}!\n"
        f"Sieger des Tippspiels {season.name}: {hof.winner_display_name} mit {hof.winner_points} Punkten.\n"
        "Die Saison wurde in die Hall of Fame aufgenommen."
    )
    await bot.post(
        session,
        SystemMessageType.CHAMPION,
        text,
        {
            "season": {"id": season.id, "name": season.name},
            "champion": bot.team_payload(sb.winner_team),
            "winner": {"display_name": hof.winner_display_name, "points": hof.winner_points},
            "leaderboard": standings[:5],
        },
        season_id=season.id,
        match_id=sb.id,
        dedupe_key=f"CHAMPION:{season.id}:{sb.winner_team_id}:{hof.winner_display_name}:{hof.winner_points}"[:120],
    )
    await notify_all(
        session,
        "SEASON_COMPLETED",
        f"{hof.winner_display_name} gewinnt das Tippspiel {season.name}!",
        f"Super-Bowl-Champion: {champion}",
        "/hall-of-fame",
    )
    audit(
        session,
        principal,
        "SEASON_COMPLETED",
        "season",
        season.id,
        None,
        {"winner": hof.winner_display_name, "points": hof.winner_points, "champion_team_id": sb.winner_team_id},
        source="SYSTEM",
    )
    await publish(session, "season_updated", season_id=season.id)
    return hof


async def reset_result(session: AsyncSession, match_id: int, principal: Principal) -> Match:
    """Undo a FINAL result (back to LOCKED) – e.g. to correct a wrong entry. Caller commits."""
    match = await lock_match(session, match_id)
    season = await lock_season(session, match.season_id)
    if match.status != MatchStatus.FINAL:
        raise conflict("Nur gewertete Spiele (FINAL) können zurückgesetzt werden.")
    matches = await load_matches(session, season.id)
    by_slot = {m.slot: m for m in matches}
    for slot in downstream_slots(match.slot):
        dm = by_slot.get(slot)
        if dm is not None and dm.status == MatchStatus.FINAL:
            raise conflict(f"Das Folgespiel {slot} ist bereits gewertet. Bitte zuerst dieses zurücksetzen.")

    old = match_snapshot(match)
    match.status = MatchStatus.LOCKED
    match.home_score = match.away_score = None
    match.winner_team_id = None
    match.result_source = None
    match.finalized_at = None
    await session.execute(delete(Score).where(Score.match_id == match.id))
    await session.flush()

    # clear automatically assigned pairings that no longer follow from the results
    matches = await load_matches(session, season.id)
    targets = actual_advancements(team_seeds(await load_season_teams(session, season.id)), match_states(matches))
    for m in matches:
        if m.slot in downstream_slots(match.slot) and m.slot not in targets and m.teams_known and not is_locked(m):
            before = match_snapshot(m)
            m.home_team_id = m.away_team_id = None
            audit(session, principal, "MATCH_TEAMS_CLEARED", "match", m.id, before, match_snapshot(m), source="SYSTEM")

    if season.status == SeasonStatus.COMPLETED and match.round == Round.SUPER_BOWL:
        other_active = (
            await session.execute(select(Season.id).where(Season.status == SeasonStatus.ACTIVE, Season.id != season.id))
        ).scalar_one_or_none()
        season.status = SeasonStatus.COMPLETED if other_active else SeasonStatus.ACTIVE
        season.champion_team_id = None
        season.completed_at = None
        await session.execute(delete(HallOfFame).where(HallOfFame.season_id == season.id))

    await recompute_leaderboard(session, season)
    audit(session, principal, "MATCH_RESULT_RESET", "match", match.id, old, match_snapshot(match), source="ADMIN")
    await bot.post(
        session,
        SystemMessageType.CORRECTION,
        f"KORREKTUR\nDas Ergebnis von {match_label(match)} wurde zurückgesetzt und wird neu ausgewertet.",
        {"match": bot.match_payload(match), "reset": True},
        season_id=season.id,
        match_id=match.id,
    )
    await publish(session, "match_updated", season_id=season.id, match_id=match.id)
    return match
