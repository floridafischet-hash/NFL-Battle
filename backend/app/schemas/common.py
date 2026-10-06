from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Conference, MatchStatus, Round, SeasonStatus


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TeamOut(ORM):
    id: int
    name: str
    short_name: str
    abbreviation: str
    city: str | None = None
    conference: Conference
    division: str | None = None
    logo_url: str | None = None
    primary_color: str
    secondary_color: str
    is_active: bool = True
    seed: int | None = None


class UserSummary(ORM):
    id: uuid.UUID
    username: str
    display_name: str
    avatar_url: str | None = None
    is_bot: bool = False


class SeasonOut(ORM):
    id: int
    name: str
    year: int
    status: SeasonStatus
    winner_points: int
    exact_score_points: int
    champion_bonus: int
    score_tips_enabled: bool
    lock_minutes_before_kickoff: int
    champion_team: TeamOut | None = None
    completed_at: datetime | None = None


class MatchOut(BaseModel):
    id: int
    season_id: int
    slot: str
    round: Round
    round_label: str
    conference: Conference | None
    home_team: TeamOut | None
    away_team: TeamOut | None
    kickoff_at: datetime | None
    lock_at: datetime | None
    venue: str | None
    status: MatchStatus
    locked: bool
    home_score: int | None
    away_score: int | None
    winner_team_id: int | None
    result_source: str | None = None
    finalized_at: datetime | None = None


class PickIn(BaseModel):
    winner_team_id: int
    winner_score: int | None = Field(default=None, ge=0, le=99)
    loser_score: int | None = Field(default=None, ge=0, le=99)


class PickOut(BaseModel):
    winner_team_id: int
    winner_score: int | None = None
    loser_score: int | None = None


class Message(BaseModel):
    detail: str
