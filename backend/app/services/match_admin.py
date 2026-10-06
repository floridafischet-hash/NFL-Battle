"""Admin operations on seasons, participants and matches."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.models import Match, Score, Season, SeasonTeam, Team
from app.models.enums import Conference, MatchStatus, Round, SeasonStatus, SystemMessageType
from app.realtime.events import publish
from app.services import bot
from app.services.audit import audit
from app.services.bracket_engine import WILD_CARD_SEEDS, wild_card_slot
from app.services.notifications import notify_all
from app.services.results import announce_matchups, conflict, lock_match, lock_season, match_snapshot
from app.services.scoring import recompute_leaderboard
from app.services.seasons import create_slot_matches, load_matches, load_season_teams, match_label, now_utc


def unprocessable(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail)


async def create_season(
    session: AsyncSession, principal: Principal | None, name: str, year: int, config: dict[str, Any]
) -> Season:
    if (await session.execute(select(Season.id).where((Season.year == year) | (Season.name == name)))).first():
        raise conflict("Eine Saison mit diesem Jahr/Namen existiert bereits.")
    season = Season(name=name, year=year, status=SeasonStatus.DRAFT, **config)
    session.add(season)
    await session.flush()
    for match in create_slot_matches(season):
        session.add(match)
    audit(
        session,
        principal,
        "SEASON_CREATED",
        "season",
        season.id,
        None,
        {"name": name, "year": year, **config},
        source="ADMIN",
    )
    await session.flush()
    return season


async def activate_season(session: AsyncSession, principal: Principal | None, season: Season) -> None:
    if season.status == SeasonStatus.ACTIVE:
        return
    current = (await session.execute(select(Season).where(Season.status == SeasonStatus.ACTIVE))).scalar_one_or_none()
    if current is not None:
        raise conflict(f"Saison {current.name} ist noch aktiv. Bitte zuerst abschließen.")
    if season.status == SeasonStatus.COMPLETED:
        raise conflict("Eine abgeschlossene Saison kann nicht erneut aktiviert werden.")
    season.status = SeasonStatus.ACTIVE
    audit(
        session,
        principal,
        "SEASON_ACTIVATED",
        "season",
        season.id,
        {"status": "DRAFT"},
        {"status": "ACTIVE"},
        source="ADMIN",
    )
    await publish(session, "season_updated", season_id=season.id)


async def set_participants(
    session: AsyncSession, principal: Principal, season: Season, entries: list[tuple[int, int]]
) -> list[SeasonTeam]:
    """Replace the seeded playoff field. entries = [(team_id, seed)]."""
    teams = {
        t.id: t for t in (await session.execute(select(Team).where(Team.id.in_([e[0] for e in entries])))).scalars()
    }
    seen: set[tuple[Conference, int]] = set()
    seen_teams: set[int] = set()
    for team_id, seed in entries:
        team = teams.get(team_id)
        if team is None:
            raise unprocessable(f"Team {team_id} existiert nicht.")
        if not 1 <= seed <= 7:
            raise unprocessable("Seeds müssen zwischen 1 und 7 liegen.")
        key = (team.conference, seed)
        if key in seen:
            raise unprocessable(f"Seed {seed} ist in der {team.conference.value} doppelt vergeben.")
        if team_id in seen_teams:
            raise unprocessable(f"{team.short_name} ist doppelt eingetragen.")
        seen.add(key)
        seen_teams.add(team_id)

    used = set()
    for m in await load_matches(session, season.id):
        used.update(t for t in (m.home_team_id, m.away_team_id) if t is not None)
    missing = used - seen_teams
    if missing:
        names = ", ".join(
            t.short_name for t in (await session.execute(select(Team).where(Team.id.in_(missing)))).scalars()
        )
        raise conflict(f"Diese Teams sind bereits Spielen zugeordnet und können nicht entfernt werden: {names}")

    old = [{"team_id": st.team_id, "seed": st.seed} for st in await load_season_teams(session, season.id)]
    await session.execute(delete(SeasonTeam).where(SeasonTeam.season_id == season.id))
    await session.flush()
    for team_id, seed in entries:
        session.add(SeasonTeam(season_id=season.id, team_id=team_id, conference=teams[team_id].conference, seed=seed))
    audit(
        session,
        principal,
        "SEASON_TEAMS_SET",
        "season",
        season.id,
        {"teams": old},
        {"teams": [{"team_id": t, "seed": s} for t, s in entries]},
        source="ADMIN",
    )
    await session.flush()
    await publish(session, "season_updated", season_id=season.id)
    return await load_season_teams(session, season.id)


def compute_lock_at(season: Season, kickoff: datetime | None) -> datetime | None:
    if kickoff is None:
        return None
    return kickoff - timedelta(minutes=season.lock_minutes_before_kickoff)


async def validate_team_for_slot(session: AsyncSession, season: Season, match: Match, team_id: int | None) -> None:
    if team_id is None:
        return
    st = await session.get(SeasonTeam, (season.id, team_id))
    if st is None:
        raise unprocessable("Das Team ist kein Playoff-Teilnehmer dieser Saison (zuerst in der Setzliste eintragen).")
    if match.conference is not None and st.conference != match.conference:
        raise unprocessable(f"Das Team gehört nicht zur {match.conference.value}.")


async def update_match(session: AsyncSession, principal: Principal, match_id: int, changes: dict[str, Any]) -> Match:
    match = await lock_match(session, match_id)
    season = await session.get(Season, match.season_id)
    assert season is not None
    old = match_snapshot(match)

    if "home_team_id" in changes or "away_team_id" in changes:
        if match.status == MatchStatus.FINAL:
            raise conflict("Bei gewerteten Spielen können die Teams nicht geändert werden.")
        home = changes.get("home_team_id", match.home_team_id)
        away = changes.get("away_team_id", match.away_team_id)
        if home is not None and home == away:
            raise unprocessable("Ein Team kann nicht gegen sich selbst spielen.")
        await validate_team_for_slot(session, season, match, home)
        await validate_team_for_slot(session, season, match, away)
        if match.round == Round.SUPER_BOWL and home and away:
            confs = {(await session.get(Team, t)).conference for t in (home, away)}  # type: ignore[union-attr]
            if len(confs) != 2:
                raise unprocessable("Im Super Bowl spielen der AFC- und der NFC-Champion gegeneinander.")
        # a team can only appear once per round
        others = [m for m in await load_matches(session, season.id) if m.round == match.round and m.id != match.id]
        for t in (home, away):
            if t is not None and any(t in (o.home_team_id, o.away_team_id) for o in others):
                raise unprocessable("Dieses Team ist in dieser Runde bereits einem anderen Spiel zugeordnet.")
        match.home_team_id, match.away_team_id = home, away

    if "kickoff_at" in changes:
        match.kickoff_at = changes["kickoff_at"]
        if "lock_at" not in changes and match.status == MatchStatus.OPEN:
            match.lock_at = compute_lock_at(season, match.kickoff_at)
    if "lock_at" in changes:
        match.lock_at = changes["lock_at"]
    if "venue" in changes:
        match.venue = (changes["venue"] or None) and changes["venue"][:120]

    await session.flush()
    await session.refresh(match)
    new = match_snapshot(match)
    if new != old or "venue" in changes:
        audit(
            session, principal, "MATCH_UPDATED", "match", match.id, old, {**new, "venue": match.venue}, source="ADMIN"
        )
    await publish(session, "match_updated", season_id=season.id, match_id=match.id)
    return match


async def change_status(
    session: AsyncSession, principal: Principal, match_id: int, action: str, lock_at: datetime | None = None
) -> Match:
    match = await lock_match(session, match_id)
    season = await lock_season(session, match.season_id)
    old = match_snapshot(match)
    now = now_utc()
    if action == "lock":
        if match.status != MatchStatus.OPEN:
            raise conflict("Nur offene Spiele können gesperrt werden.")
        match.status = MatchStatus.LOCKED
        audit_action = "MATCH_LOCKED"
    elif action in {"open", "reopen"}:
        if match.status == MatchStatus.FINAL:
            raise conflict("Gewertete Spiele bitte zuerst über 'Ergebnis zurücksetzen' öffnen.")
        if lock_at is not None and lock_at <= now:
            raise unprocessable("Die neue Deadline muss in der Zukunft liegen.")
        was_void = match.status == MatchStatus.VOID
        match.status = MatchStatus.OPEN
        if lock_at is not None:
            match.lock_at = lock_at
        elif match.lock_at is not None and match.lock_at <= now:
            match.lock_at = None  # no automatic re-lock; admin locks manually
        audit_action = "MATCH_REOPENED"
        if was_void:
            await recompute_leaderboard(session, season)
    elif action == "void":
        if match.status == MatchStatus.FINAL:
            raise conflict("Bitte zuerst das Ergebnis zurücksetzen.")
        match.status = MatchStatus.VOID
        await session.execute(delete(Score).where(Score.match_id == match.id))
        await recompute_leaderboard(session, season)
        audit_action = "MATCH_VOIDED"
    else:
        raise unprocessable("Unbekannte Aktion.")
    await session.flush()
    audit(session, principal, audit_action, "match", match.id, old, match_snapshot(match), source="ADMIN")
    if action in {"open", "reopen"} and old["status"] != "OPEN":
        await notify_all(session, "MATCH_REOPENED", f"Tipps wieder offen: {match_label(match)}", None, "/bracket")
    await publish(session, "match_updated", season_id=season.id, match_id=match.id)
    return match


async def generate_wild_card(session: AsyncSession, principal: Principal, season: Season) -> list[Match]:
    """Create the 2v7, 3v6, 4v5 pairings of both conferences from the seeds."""
    seeds = {(st.conference, st.seed): st.team_id for st in await load_season_teams(session, season.id)}
    matches = {m.slot: m for m in await load_matches(session, season.id)}
    for conf in (Conference.AFC, Conference.NFC):
        missing = [n for n in range(1, 8) if (conf, n) not in seeds]
        if missing:
            missing_text = ", ".join(map(str, missing))
            raise unprocessable(
                f"Für die {conf.value} fehlen Seeds: {missing_text} (benötigt: 1–7, Seed 1 hat ein Freilos)."
            )
    changed = []
    for conf in (Conference.AFC, Conference.NFC):
        for index, (home_seed, away_seed) in WILD_CARD_SEEDS.items():
            home, away = seeds.get((conf, home_seed)), seeds.get((conf, away_seed))
            if home is None or away is None:
                raise unprocessable(f"Für die {conf.value} fehlen Seeds (benötigt: 1–7).")
            m = matches[wild_card_slot(conf, index)]
            if m.status != MatchStatus.OPEN:
                raise conflict(f"{m.slot} ist bereits gesperrt/gewertet.")
            if (m.home_team_id, m.away_team_id) != (home, away):
                old = match_snapshot(m)
                m.home_team_id, m.away_team_id = home, away
                await session.flush()
                await session.refresh(m, ["home_team", "away_team"])
                audit(session, principal, "MATCH_TEAMS_ASSIGNED", "match", m.id, old, match_snapshot(m), source="ADMIN")
            changed.append(m)
    await announce_matchups(session, season, changed, SystemMessageType.MATCHUP)
    await notify_all(session, "MATCHUPS", "Die Wild-Card-Paarungen stehen fest – jetzt tippen!", None, "/bracket")
    await publish(session, "match_updated", season_id=season.id)
    return changed


async def announce_open_matchups(session: AsyncSession, season: Season) -> int:
    """Post all currently known but not yet started pairings (after manual drag & drop)."""
    matches = [m for m in await load_matches(session, season.id) if m.teams_known and m.status == MatchStatus.OPEN]
    if not matches:
        raise unprocessable("Es gibt keine offenen Paarungen mit feststehenden Teams.")
    for m in matches:
        await session.refresh(m, ["home_team", "away_team"])
    await announce_matchups(session, season, matches, SystemMessageType.MATCHUP)
    await notify_all(
        session, "MATCHUPS", "Neue Paarungen – jetzt tippen!", ", ".join(match_label(m) for m in matches), "/bracket"
    )
    return len(matches)


async def post_info(session: AsyncSession, text: str, season_id: int | None = None) -> None:
    await bot.post(session, SystemMessageType.INFO, text, {}, season_id=season_id)
