"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-06 14:49:07.786420
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("short_name", sa.String(length=40), nullable=False),
        sa.Column("abbreviation", sa.String(length=4), nullable=False),
        sa.Column("city", sa.String(length=60), nullable=True),
        sa.Column(
            "conference",
            sa.Enum("AFC", "NFC", name="conference", native_enum=False, create_constraint=False, length=24),
            nullable=False,
        ),
        sa.Column("division", sa.String(length=10), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("primary_color", sa.String(length=7), nullable=False),
        sa.Column("secondary_color", sa.String(length=7), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("conference IN ('AFC', 'NFC')", name=op.f("ck_teams_conference")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teams")),
        sa.UniqueConstraint("abbreviation", name=op.f("uq_teams_abbreviation")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column(
            "role",
            sa.Enum("USER", "ADMIN", "AGENT", name="user_role", native_enum=False, create_constraint=False, length=24),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_bot", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('USER', 'ADMIN', 'AGENT')", name=op.f("ck_users_user_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
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
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actor_type", sa.String(length=10), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_label", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("object_type", sa.String(length=40), nullable=False),
        sa.Column("object_id", sa.String(length=64), nullable=True),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name=op.f("fk_audit_logs_actor_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)
    op.create_index("ix_audit_logs_object", "audit_logs", ["object_type", "object_id"], unique=False)
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(length=300), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_notifications_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "read_at"], unique=False)
    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "ACTIVE",
                "COMPLETED",
                name="season_status",
                native_enum=False,
                create_constraint=False,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column("winner_points", sa.Integer(), nullable=False),
        sa.Column("exact_score_points", sa.Integer(), nullable=False),
        sa.Column("champion_bonus", sa.Integer(), nullable=False),
        sa.Column("score_tips_enabled", sa.Boolean(), nullable=False),
        sa.Column("lock_minutes_before_kickoff", sa.Integer(), nullable=False),
        sa.Column("champion_team_id", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'COMPLETED')", name=op.f("ck_seasons_season_status")),
        sa.CheckConstraint(
            "champion_bonus >= 0 AND champion_bonus <= 100", name=op.f("ck_seasons_champion_bonus_range")
        ),
        sa.CheckConstraint(
            "exact_score_points >= 0 AND exact_score_points <= 100", name=op.f("ck_seasons_exact_points_range")
        ),
        sa.CheckConstraint(
            "lock_minutes_before_kickoff >= 0 AND lock_minutes_before_kickoff <= 10080",
            name=op.f("ck_seasons_lock_minutes_range"),
        ),
        sa.CheckConstraint("winner_points >= 0 AND winner_points <= 100", name=op.f("ck_seasons_winner_points_range")),
        sa.ForeignKeyConstraint(
            ["champion_team_id"], ["teams.id"], name=op.f("fk_seasons_champion_team_id_teams"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seasons")),
        sa.UniqueConstraint("name", name=op.f("uq_seasons_name")),
        sa.UniqueConstraint("year", name=op.f("uq_seasons_year")),
    )
    op.create_index(
        "uq_seasons_single_active", "seasons", ["status"], unique=True, postgresql_where=sa.text("status = 'ACTIVE'")
    )
    op.create_table(
        "uploads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "CHAT", "AVATAR", "LOGO", name="upload_kind", native_enum=False, create_constraint=False, length=24
            ),
            nullable=False,
        ),
        sa.Column("path", sa.String(length=300), nullable=False),
        sa.Column("content_type", sa.String(length=60), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('CHAT', 'AVATAR', 'LOGO')", name=op.f("ck_uploads_upload_kind")),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["users.id"], name=op.f("fk_uploads_uploaded_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploads")),
        sa.UniqueConstraint("path", name=op.f("uq_uploads_path")),
    )
    op.create_table(
        "brackets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["season_id"], ["seasons.id"], name=op.f("fk_brackets_season_id_seasons"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_brackets_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brackets")),
        sa.UniqueConstraint("user_id", "season_id", name="uq_brackets_user_season"),
    )
    op.create_index(op.f("ix_brackets_season_id"), "brackets", ["season_id"], unique=False)
    op.create_table(
        "hall_of_fame",
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("winner_user_id", sa.Uuid(), nullable=True),
        sa.Column("winner_display_name", sa.String(length=80), nullable=False),
        sa.Column("winner_points", sa.Integer(), nullable=False),
        sa.Column("winner_correct_winners", sa.Integer(), nullable=False),
        sa.Column("winner_exact_scores", sa.Integer(), nullable=False),
        sa.Column("champion_team_id", sa.Integer(), nullable=True),
        sa.Column("winner_sb_pick_team_id", sa.Integer(), nullable=True),
        sa.Column("final_standings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["champion_team_id"], ["teams.id"], name=op.f("fk_hall_of_fame_champion_team_id_teams"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["season_id"], ["seasons.id"], name=op.f("fk_hall_of_fame_season_id_seasons"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["winner_sb_pick_team_id"],
            ["teams.id"],
            name=op.f("fk_hall_of_fame_winner_sb_pick_team_id_teams"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["winner_user_id"], ["users.id"], name=op.f("fk_hall_of_fame_winner_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("season_id", name=op.f("pk_hall_of_fame")),
    )
    op.create_table(
        "leaderboards",
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("previous_rank", sa.Integer(), nullable=True),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("correct_winners", sa.Integer(), nullable=False),
        sa.Column("wrong_picks", sa.Integer(), nullable=False),
        sa.Column("missed_picks", sa.Integer(), nullable=False),
        sa.Column("exact_scores", sa.Integer(), nullable=False),
        sa.Column("champion_correct", sa.Boolean(), nullable=False),
        sa.Column("scored_matches", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["season_id"], ["seasons.id"], name=op.f("fk_leaderboards_season_id_seasons"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_leaderboards_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("season_id", "user_id", name=op.f("pk_leaderboards")),
    )
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column(
            "round",
            sa.Enum(
                "WILD_CARD",
                "DIVISIONAL",
                "CONFERENCE",
                "SUPER_BOWL",
                name="match_round",
                native_enum=False,
                create_constraint=False,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column(
            "conference",
            sa.Enum("AFC", "NFC", name="conference", native_enum=False, create_constraint=False, length=24),
            nullable=True,
        ),
        sa.Column("slot", sa.String(length=16), nullable=False),
        sa.Column("home_team_id", sa.Integer(), nullable=True),
        sa.Column("away_team_id", sa.Integer(), nullable=True),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("venue", sa.String(length=120), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "LOCKED",
                "FINAL",
                "VOID",
                name="match_status",
                native_enum=False,
                create_constraint=False,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("winner_team_id", sa.Integer(), nullable=True),
        sa.Column(
            "result_source",
            sa.Enum("ADMIN", "AGENT", name="result_source", native_enum=False, create_constraint=False, length=24),
            nullable=True,
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_check_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_set_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("conference IN ('AFC', 'NFC')", name=op.f("ck_matches_conference")),
        sa.CheckConstraint("result_source IN ('ADMIN', 'AGENT')", name=op.f("ck_matches_result_source")),
        sa.CheckConstraint(
            "round IN ('WILD_CARD', 'DIVISIONAL', 'CONFERENCE', 'SUPER_BOWL')", name=op.f("ck_matches_match_round")
        ),
        sa.CheckConstraint("status IN ('OPEN', 'LOCKED', 'FINAL', 'VOID')", name=op.f("ck_matches_match_status")),
        sa.CheckConstraint(
            "(home_score IS NULL AND away_score IS NULL) OR (home_score >= 0 AND away_score >= 0)",
            name=op.f("ck_matches_scores_valid"),
        ),
        sa.CheckConstraint(
            "home_team_id IS NULL OR away_team_id IS NULL OR home_team_id <> away_team_id",
            name=op.f("ck_matches_distinct_teams"),
        ),
        sa.ForeignKeyConstraint(
            ["away_team_id"], ["teams.id"], name=op.f("fk_matches_away_team_id_teams"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["home_team_id"], ["teams.id"], name=op.f("fk_matches_home_team_id_teams"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["result_set_by"], ["users.id"], name=op.f("fk_matches_result_set_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["season_id"], ["seasons.id"], name=op.f("fk_matches_season_id_seasons"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["winner_team_id"], ["teams.id"], name=op.f("fk_matches_winner_team_id_teams"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matches")),
        sa.UniqueConstraint("season_id", "slot", name="uq_matches_season_slot"),
    )
    op.create_index(op.f("ix_matches_season_id"), "matches", ["season_id"], unique=False)
    op.create_index("ix_matches_status_lock_at", "matches", ["status", "lock_at"], unique=False)
    op.create_table(
        "season_teams",
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column(
            "conference",
            sa.Enum("AFC", "NFC", name="conference", native_enum=False, create_constraint=False, length=24),
            nullable=False,
        ),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.CheckConstraint("conference IN ('AFC', 'NFC')", name=op.f("ck_season_teams_conference")),
        sa.CheckConstraint("seed >= 1 AND seed <= 7", name=op.f("ck_season_teams_seed_range")),
        sa.ForeignKeyConstraint(
            ["season_id"], ["seasons.id"], name=op.f("fk_season_teams_season_id_seasons"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name=op.f("fk_season_teams_team_id_teams"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("season_id", "team_id", name=op.f("pk_season_teams")),
        sa.UniqueConstraint("season_id", "conference", "seed", name="uq_season_teams_seed"),
    )
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_label", sa.String(length=120), nullable=False),
        sa.Column("agent_token_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "APPLIED",
                "DUPLICATE",
                "PENDING_CONFIRMATION",
                "REVIEW_REQUIRED",
                "REJECTED",
                "ERROR",
                "OK",
                name="agent_run_status",
                native_enum=False,
                create_constraint=False,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column("match_id", sa.Integer(), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('APPLIED', 'DUPLICATE', 'PENDING_CONFIRMATION', 'REVIEW_REQUIRED', 'REJECTED', 'ERROR', 'OK')",
            name=op.f("ck_agent_runs_agent_run_status"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_token_id"],
            ["agent_tokens.id"],
            name=op.f("fk_agent_runs_agent_token_id_agent_tokens"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"], ["matches.id"], name=op.f("fk_agent_runs_match_id_matches"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_index("ix_agent_runs_started_at", "agent_runs", ["started_at"], unique=False)
    op.create_table(
        "prediction_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("old_winner_team_id", sa.Integer(), nullable=True),
        sa.Column("old_winner_score", sa.Integer(), nullable=True),
        sa.Column("old_loser_score", sa.Integer(), nullable=True),
        sa.Column("new_winner_team_id", sa.Integer(), nullable=False),
        sa.Column("new_winner_score", sa.Integer(), nullable=True),
        sa.Column("new_loser_score", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "APPROVED",
                "REJECTED",
                "CANCELLED",
                name="change_request_status",
                native_enum=False,
                create_constraint=False,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')",
            name=op.f("ck_prediction_changes_change_request_status"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["users.id"], name=op.f("fk_prediction_changes_decided_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["match_id"], ["matches.id"], name=op.f("fk_prediction_changes_match_id_matches"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["new_winner_team_id"],
            ["teams.id"],
            name=op.f("fk_prediction_changes_new_winner_team_id_teams"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["old_winner_team_id"],
            ["teams.id"],
            name=op.f("fk_prediction_changes_old_winner_team_id_teams"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_prediction_changes_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prediction_changes")),
    )
    op.create_index(
        "uq_prediction_changes_pending",
        "prediction_changes",
        ["user_id", "match_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bracket_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("winner_team_id", sa.Integer(), nullable=False),
        sa.Column("winner_score", sa.Integer(), nullable=True),
        sa.Column("loser_score", sa.Integer(), nullable=True),
        sa.Column("updated_via", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(winner_score IS NULL AND loser_score IS NULL) OR (winner_score > loser_score AND loser_score >= 0 AND winner_score <= 99)",
            name=op.f("ck_predictions_score_tip_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["bracket_id"], ["brackets.id"], name=op.f("fk_predictions_bracket_id_brackets"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["match_id"], ["matches.id"], name=op.f("fk_predictions_match_id_matches"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["winner_team_id"], ["teams.id"], name=op.f("fk_predictions_winner_team_id_teams"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_predictions")),
        sa.UniqueConstraint("bracket_id", "match_id", name="uq_predictions_bracket_match"),
    )
    op.create_index(op.f("ix_predictions_match_id"), "predictions", ["match_id"], unique=False)
    op.create_table(
        "system_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "MATCHUP",
                "KICKOFF",
                "HALFTIME",
                "FINAL",
                "CORRECTION",
                "LEADERBOARD",
                "OPEN_PICKS",
                "NEXT_ROUND",
                "CHAMPION",
                "INFO",
                name="system_message_type",
                native_enum=False,
                create_constraint=False,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column("season_id", sa.Integer(), nullable=True),
        sa.Column("match_id", sa.Integer(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dedupe_key", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "type IN ('MATCHUP', 'KICKOFF', 'HALFTIME', 'FINAL', 'CORRECTION', 'LEADERBOARD', 'OPEN_PICKS', 'NEXT_ROUND', 'CHAMPION', 'INFO')",
            name=op.f("ck_system_messages_system_message_type"),
        ),
        sa.ForeignKeyConstraint(
            ["match_id"], ["matches.id"], name=op.f("fk_system_messages_match_id_matches"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["season_id"], ["seasons.id"], name=op.f("fk_system_messages_season_id_seasons"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_messages")),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_system_messages_dedupe_key")),
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=True),
        sa.Column("system_message_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["users.id"], name=op.f("fk_chat_messages_deleted_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["system_message_id"],
            ["system_messages.id"],
            name=op.f("fk_chat_messages_system_message_id_system_messages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"], ["uploads.id"], name=op.f("fk_chat_messages_upload_id_uploads"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_chat_messages_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"], unique=False)
    op.create_table(
        "result_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=True),
        sa.Column("agent_label", sa.String(length=120), nullable=False),
        sa.Column("home_score", sa.Integer(), nullable=False),
        sa.Column("away_score", sa.Integer(), nullable=False),
        sa.Column("winner_team_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING_CONFIRMATION",
                "APPLIED",
                "REVIEW_REQUIRED",
                "REJECTED",
                "DUPLICATE",
                "SUPERSEDED",
                name="report_status",
                native_enum=False,
                create_constraint=False,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING_CONFIRMATION', 'APPLIED', 'REVIEW_REQUIRED', 'REJECTED', 'DUPLICATE', 'SUPERSEDED')",
            name=op.f("ck_result_reports_report_status"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_runs.id"],
            name=op.f("fk_result_reports_agent_run_id_agent_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"], ["matches.id"], name=op.f("fk_result_reports_match_id_matches"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"], ["users.id"], name=op.f("fk_result_reports_reviewed_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["winner_team_id"], ["teams.id"], name=op.f("fk_result_reports_winner_team_id_teams"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_result_reports")),
    )
    op.create_index("ix_result_reports_match_status", "result_reports", ["match_id", "status"], unique=False)
    op.create_table(
        "scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("prediction_id", sa.Integer(), nullable=True),
        sa.Column("winner_correct", sa.Boolean(), nullable=False),
        sa.Column("exact_correct", sa.Boolean(), nullable=False),
        sa.Column("has_pick", sa.Boolean(), nullable=False),
        sa.Column("base_points", sa.Integer(), nullable=False),
        sa.Column("bonus_points", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["match_id"], ["matches.id"], name=op.f("fk_scores_match_id_matches"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["prediction_id"], ["predictions.id"], name=op.f("fk_scores_prediction_id_predictions"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["season_id"], ["seasons.id"], name=op.f("fk_scores_season_id_seasons"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_scores_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scores")),
        sa.UniqueConstraint("user_id", "match_id", name="uq_scores_user_match"),
    )
    op.create_index(op.f("ix_scores_season_id"), "scores", ["season_id"], unique=False)

    # Audit log is append-only: block UPDATE and DELETE on database level.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_logs_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE TRIGGER audit_logs_no_update BEFORE UPDATE OR DELETE ON audit_logs "
        "FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_immutable()")
    op.drop_index(op.f("ix_scores_season_id"), table_name="scores")
    op.drop_table("scores")
    op.drop_index("ix_result_reports_match_status", table_name="result_reports")
    op.drop_table("result_reports")
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_table("system_messages")
    op.drop_index(op.f("ix_predictions_match_id"), table_name="predictions")
    op.drop_table("predictions")
    op.drop_index(
        "uq_prediction_changes_pending", table_name="prediction_changes", postgresql_where=sa.text("status = 'PENDING'")
    )
    op.drop_table("prediction_changes")
    op.drop_index("ix_agent_runs_started_at", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_table("season_teams")
    op.drop_index("ix_matches_status_lock_at", table_name="matches")
    op.drop_index(op.f("ix_matches_season_id"), table_name="matches")
    op.drop_table("matches")
    op.drop_table("leaderboards")
    op.drop_table("hall_of_fame")
    op.drop_index(op.f("ix_brackets_season_id"), table_name="brackets")
    op.drop_table("brackets")
    op.drop_table("uploads")
    op.drop_index("uq_seasons_single_active", table_name="seasons", postgresql_where=sa.text("status = 'ACTIVE'"))
    op.drop_table("seasons")
    op.drop_index("ix_notifications_user_read", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_audit_logs_object", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("agent_tokens")
    op.drop_table("users")
    op.drop_table("teams")
