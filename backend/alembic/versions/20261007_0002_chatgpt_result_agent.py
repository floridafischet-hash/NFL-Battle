"""ChatGPT result agent replaces the external OpenClaw API

* drops the agent API tokens (external machine access is no longer possible)
* agent runs get the status NO_RESULT (ChatGPT found no final result yet)
* the user role AGENT is gone (it was never assignable to users)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07 07:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUN_STATUSES = "'APPLIED', 'DUPLICATE', 'PENDING_CONFIRMATION', 'REVIEW_REQUIRED', 'REJECTED', 'ERROR', 'OK'"


def upgrade() -> None:
    op.drop_constraint(op.f("fk_agent_runs_agent_token_id_agent_tokens"), "agent_runs", type_="foreignkey")
    op.drop_column("agent_runs", "agent_token_id")
    op.drop_table("agent_tokens")

    op.drop_constraint(op.f("ck_agent_runs_agent_run_status"), "agent_runs", type_="check")
    op.create_check_constraint(
        op.f("ck_agent_runs_agent_run_status"), "agent_runs", f"status IN ({RUN_STATUSES}, 'NO_RESULT')"
    )
    op.create_index("ix_agent_runs_match_kind_started", "agent_runs", ["match_id", "kind", "started_at"])

    op.drop_constraint(op.f("ck_users_user_role"), "users", type_="check")
    op.create_check_constraint(op.f("ck_users_user_role"), "users", "role IN ('USER', 'ADMIN')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_users_user_role"), "users", type_="check")
    op.create_check_constraint(op.f("ck_users_user_role"), "users", "role IN ('USER', 'ADMIN', 'AGENT')")

    op.drop_index("ix_agent_runs_match_kind_started", table_name="agent_runs")
    op.execute("UPDATE agent_runs SET status = 'OK' WHERE status = 'NO_RESULT'")
    op.drop_constraint(op.f("ck_agent_runs_agent_run_status"), "agent_runs", type_="check")
    op.create_check_constraint(op.f("ck_agent_runs_agent_run_status"), "agent_runs", f"status IN ({RUN_STATUSES})")

    op.create_table(
        "agent_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("token_prefix", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_agent_tokens_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_agent_tokens_token_hash")),
    )
    op.add_column("agent_runs", sa.Column("agent_token_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_agent_runs_agent_token_id_agent_tokens"),
        "agent_runs",
        "agent_tokens",
        ["agent_token_id"],
        ["id"],
        ondelete="SET NULL",
    )
