import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, str_enum, utcnow
from app.models.enums import AgentRunStatus, ReportStatus
from app.models.season import Match, Team


class AgentRun(Base):
    """Every step of the ChatGPT result agent (research call, validation, admin check request)."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_started_at", "started_at"),
        Index("ix_agent_runs_match_kind_started", "match_id", "kind", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_label: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[AgentRunStatus] = mapped_column(str_enum(AgentRunStatus, "agent_run_status"), nullable=False)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id", ondelete="SET NULL"))
    request_payload: Mapped[dict | None] = mapped_column(JSONB)
    message: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResultReport(Base):
    """A result found by the ChatGPT result agent including its sources (provenance)."""

    __tablename__ = "result_reports"
    __table_args__ = (Index("ix_result_reports_match_status", "match_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"))
    agent_label: Mapped[str] = mapped_column(String(120), nullable=False)
    home_score: Mapped[int] = mapped_column(Integer, nullable=False)
    away_score: Mapped[int] = mapped_column(Integer, nullable=False)
    winner_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extra_sources: Mapped[list | None] = mapped_column(JSONB)
    status: Mapped[ReportStatus] = mapped_column(str_enum(ReportStatus, "report_status"), nullable=False)
    review_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, nullable=False
    )

    match: Mapped[Match] = relationship(lazy="joined")
    winner_team: Mapped[Team] = relationship(lazy="joined")
