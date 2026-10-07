from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match, Season, SeasonTeam, Team
from app.models.enums import MatchStatus, SeasonStatus
from app.schemas.common import MatchOut, TeamOut
from app.services.bracket_engine import ROUND_LABELS, SLOTS, MatchState, TeamSeed, slots_in_resolution_order


def now_utc() -> datetime:
    return datetime.now(UTC)


def is_locked(match: Match, now: datetime | None = None) -> bool:
    now = now or now_utc()
    if match.status != MatchStatus.OPEN:
        return True
    return match.lock_at is not None and now >= match.lock_at


def not_found(what: str = "Eintrag") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} nicht gefunden")


async def get_season(session: AsyncSession, season_id: int) -> Season:
    season = await session.get(Season, season_id)
    if season is None:
        raise not_found("Saison")
    return season


async def get_current_season(session: AsyncSession) -> Season | None:
    active = (await session.execute(select(Season).where(Season.status == SeasonStatus.ACTIVE))).scalar_one_or_none()
    if active is not None:
        return active
    return (
        await session.execute(
            select(Season).where(Season.status != SeasonStatus.DRAFT).order_by(Season.year.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def resolve_season(session: AsyncSession, season_id: int | None) -> Season:
    if season_id is not None:
        return await get_season(session, season_id)
    season = await get_current_season(session)
    if season is None:
        raise not_found("Aktive Saison")
    return season


async def load_matches(session: AsyncSession, season_id: int, for_update: bool = False) -> list[Match]:
    stmt = select(Match).where(Match.season_id == season_id)
    if for_update:
        stmt = stmt.with_for_update(of=Match)
    matches = list((await session.execute(stmt)).unique().scalars())
    return sorted(matches, key=lambda m: SLOTS[m.slot].order if m.slot in SLOTS else 99)


async def load_season_teams(session: AsyncSession, season_id: int) -> list[SeasonTeam]:
    return list((await session.execute(select(SeasonTeam).where(SeasonTeam.season_id == season_id))).unique().scalars())


def seed_map(season_teams: list[SeasonTeam]) -> dict[int, int]:
    return {st.team_id: st.seed for st in season_teams}


def team_seeds(season_teams: list[SeasonTeam]) -> list[TeamSeed]:
    return [TeamSeed(st.team_id, st.conference, st.seed) for st in season_teams]


def team_out(team: Team | None, seeds: dict[int, int] | None = None) -> TeamOut | None:
    if team is None:
        return None
    out = TeamOut.model_validate(team)
    if seeds:
        out.seed = seeds.get(team.id)
    return out


def match_state(match: Match, now: datetime | None = None) -> MatchState:
    return MatchState(
        slot=match.slot,
        home_team_id=match.home_team_id,
        away_team_id=match.away_team_id,
        status=match.status,
        winner_team_id=match.winner_team_id,
        locked=is_locked(match, now),
    )


def match_states(matches: list[Match], now: datetime | None = None) -> dict[str, MatchState]:
    now = now or now_utc()
    return {m.slot: match_state(m, now) for m in matches}


def match_out(match: Match, seeds: dict[int, int] | None = None, now: datetime | None = None) -> MatchOut:
    return MatchOut(
        id=match.id,
        season_id=match.season_id,
        slot=match.slot,
        round=match.round,
        round_label=ROUND_LABELS[match.round],
        conference=match.conference,
        home_team=team_out(match.home_team, seeds),
        away_team=team_out(match.away_team, seeds),
        kickoff_at=match.kickoff_at,
        lock_at=match.lock_at,
        venue=match.venue,
        status=match.status,
        locked=is_locked(match, now),
        home_score=match.home_score,
        away_score=match.away_score,
        winner_team_id=match.winner_team_id,
        result_source=match.result_source.value if match.result_source else None,
        finalized_at=match.finalized_at,
    )


def match_label(match: Match) -> str:
    home = match.home_team.short_name if match.home_team else "TBD"
    away = match.away_team.short_name if match.away_team else "TBD"
    return f"{home} vs {away}"


def create_slot_matches(season: Season) -> list[Match]:
    return [
        Match(season_id=season.id, round=s.round, conference=s.conference, slot=s.slot, status=MatchStatus.OPEN)
        for s in slots_in_resolution_order()
    ]
