import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import Conference, MatchStatus, ResultSource, Round, SeasonStatus


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    short_name: Mapped[str] = mapped_column(String(40), nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(4), unique=True, nullable=False)
    city: Mapped[str | None] = mapped_column(String(60))
    conference: Mapped[Conference] = mapped_column(str_enum(Conference, "conference"), nullable=False)
    division: Mapped[str | None] = mapped_column(String(10))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    primary_color: Mapped[str] = mapped_column(String(7), default="#334155", nullable=False)
    secondary_color: Mapped[str] = mapped_column(String(7), default="#94a3b8", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)


class Season(TimestampMixin, Base):
    __tablename__ = "seasons"
    __table_args__ = (
        Index(
            "uq_seasons_single_active",
            "status",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        CheckConstraint("winner_points >= 0 AND winner_points <= 100", name="winner_points_range"),
        CheckConstraint("exact_score_points >= 0 AND exact_score_points <= 100", name="exact_points_range"),
        CheckConstraint("champion_bonus >= 0 AND champion_bonus <= 100", name="champion_bonus_range"),
        CheckConstraint(
            "lock_minutes_before_kickoff >= 0 AND lock_minutes_before_kickoff <= 10080", name="lock_minutes_range"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    year: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    status: Mapped[SeasonStatus] = mapped_column(
        str_enum(SeasonStatus, "season_status"), default=SeasonStatus.DRAFT, nullable=False
    )
    winner_points: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    exact_score_points: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    champion_bonus: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    score_tips_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lock_minutes_before_kickoff: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    champion_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    champion_team: Mapped[Team | None] = relationship(foreign_keys=[champion_team_id], lazy="joined")


class SeasonTeam(Base):
    """Playoff participant of a season with its seed (1 = bye)."""

    __tablename__ = "season_teams"
    __table_args__ = (
        UniqueConstraint("season_id", "conference", "seed", name="uq_season_teams_seed"),
        CheckConstraint("seed >= 1 AND seed <= 7", name="seed_range"),
    )

    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), primary_key=True)
    conference: Mapped[Conference] = mapped_column(str_enum(Conference, "conference"), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)

    team: Mapped[Team] = relationship(lazy="joined")


class Match(TimestampMixin, Base):
    """One bracket slot of a season (13 per season)."""

    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("season_id", "slot", name="uq_matches_season_slot"),
        CheckConstraint(
            "home_team_id IS NULL OR away_team_id IS NULL OR home_team_id <> away_team_id",
            name="distinct_teams",
        ),
        CheckConstraint(
            "(home_score IS NULL AND away_score IS NULL) OR (home_score >= 0 AND away_score >= 0)",
            name="scores_valid",
        ),
        Index("ix_matches_status_lock_at", "status", "lock_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    round: Mapped[Round] = mapped_column(str_enum(Round, "match_round"), nullable=False)
    conference: Mapped[Conference | None] = mapped_column(str_enum(Conference, "conference"))
    slot: Mapped[str] = mapped_column(String(16), nullable=False)
    home_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    away_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lock_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    venue: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[MatchStatus] = mapped_column(
        str_enum(MatchStatus, "match_status"), default=MatchStatus.OPEN, nullable=False
    )
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    winner_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    result_source: Mapped[ResultSource | None] = mapped_column(str_enum(ResultSource, "result_source"))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_check_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_set_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))

    season: Mapped[Season] = relationship(lazy="joined")
    home_team: Mapped[Team | None] = relationship(foreign_keys=[home_team_id], lazy="joined")
    away_team: Mapped[Team | None] = relationship(foreign_keys=[away_team_id], lazy="joined")
    winner_team: Mapped[Team | None] = relationship(foreign_keys=[winner_team_id], lazy="joined")

    @property
    def teams_known(self) -> bool:
        return self.home_team_id is not None and self.away_team_id is not None

    def loser_team_id(self) -> int | None:
        if self.winner_team_id is None:
            return None
        return self.away_team_id if self.winner_team_id == self.home_team_id else self.home_team_id
