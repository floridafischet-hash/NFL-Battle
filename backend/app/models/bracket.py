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
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum, utcnow
from app.models.enums import ChangeRequestStatus
from app.models.season import Match, Season, Team
from app.models.user import User


class Bracket(TimestampMixin, Base):
    __tablename__ = "brackets"
    __table_args__ = (UniqueConstraint("user_id", "season_id", name="uq_brackets_user_season"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="joined")
    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="bracket", cascade="all, delete-orphan", lazy="selectin"
    )


class Prediction(TimestampMixin, Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("bracket_id", "match_id", name="uq_predictions_bracket_match"),
        CheckConstraint(
            "(winner_score IS NULL AND loser_score IS NULL) OR "
            "(winner_score > loser_score AND loser_score >= 0 AND winner_score <= 99)",
            name="score_tip_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bracket_id: Mapped[int] = mapped_column(ForeignKey("brackets.id", ondelete="CASCADE"), nullable=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    winner_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    winner_score: Mapped[int | None] = mapped_column(Integer)
    loser_score: Mapped[int | None] = mapped_column(Integer)
    updated_via: Mapped[str] = mapped_column(String(20), default="WEB", nullable=False)

    bracket: Mapped[Bracket] = relationship(back_populates="predictions")
    match: Mapped[Match] = relationship(lazy="joined")
    winner_team: Mapped[Team] = relationship(lazy="joined")


class PredictionChange(Base):
    """Change request for a prediction after the match was locked."""

    __tablename__ = "prediction_changes"
    __table_args__ = (
        Index(
            "uq_prediction_changes_pending",
            "user_id",
            "match_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    old_winner_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    old_winner_score: Mapped[int | None] = mapped_column(Integer)
    old_loser_score: Mapped[int | None] = mapped_column(Integer)
    new_winner_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    new_winner_score: Mapped[int | None] = mapped_column(Integer)
    new_loser_score: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ChangeRequestStatus] = mapped_column(
        str_enum(ChangeRequestStatus, "change_request_status"), default=ChangeRequestStatus.PENDING, nullable=False
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, nullable=False
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")
    decider: Mapped[User | None] = relationship(foreign_keys=[decided_by], lazy="joined")
    match: Mapped[Match] = relationship(lazy="joined")
    old_winner_team: Mapped[Team | None] = relationship(foreign_keys=[old_winner_team_id], lazy="joined")
    new_winner_team: Mapped[Team] = relationship(foreign_keys=[new_winner_team_id], lazy="joined")


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("user_id", "match_id", name="uq_scores_user_match"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("predictions.id", ondelete="SET NULL"))
    winner_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exact_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    has_pick: Mapped[bool] = mapped_column(Boolean, nullable=False)
    base_points: Mapped[int] = mapped_column(Integer, nullable=False)
    bonus_points: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, nullable=False
    )


class Leaderboard(Base):
    __tablename__ = "leaderboards"

    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_rank: Mapped[int | None] = mapped_column(Integer)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_winners: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wrong_picks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missed_picks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exact_scores: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    champion_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scored_matches: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped[User] = relationship(lazy="joined")


class HallOfFame(Base):
    __tablename__ = "hall_of_fame"

    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), primary_key=True)
    winner_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    winner_display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    winner_points: Mapped[int] = mapped_column(Integer, nullable=False)
    winner_correct_winners: Mapped[int] = mapped_column(Integer, nullable=False)
    winner_exact_scores: Mapped[int] = mapped_column(Integer, nullable=False)
    champion_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"))
    winner_sb_pick_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"))
    final_standings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, nullable=False
    )

    season: Mapped[Season] = relationship(lazy="joined")
    champion_team: Mapped[Team | None] = relationship(foreign_keys=[champion_team_id], lazy="joined")
    winner_sb_pick_team: Mapped[Team | None] = relationship(foreign_keys=[winner_sb_pick_team_id], lazy="joined")
