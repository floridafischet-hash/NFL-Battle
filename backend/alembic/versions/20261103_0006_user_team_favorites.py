"""Store NFL team favorites per user.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-03 07:00:00
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = op.create_table(
        "user_team_favorites",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("team_slug", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_team_favorites_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "team_slug", name=op.f("pk_user_team_favorites")),
    )

    connection = op.get_bind()
    old_value = connection.execute(
        sa.text("SELECT value FROM app_settings WHERE key = 'live_team_favorites'")
    ).scalar_one_or_none()
    try:
        favorites = json.loads(old_value) if old_value else []
    except (TypeError, ValueError):
        favorites = []
    if not isinstance(favorites, list):
        favorites = []

    owner_id = connection.execute(
        sa.text(
            "SELECT COALESCE("
            "(SELECT NULLIF(value, '')::uuid FROM app_settings WHERE key = 'instance_owner_user_id'), "
            "(SELECT id FROM users WHERE is_superuser = true ORDER BY created_at LIMIT 1))"
        )
    ).scalar_one_or_none()
    cleaned = list(dict.fromkeys(value for value in favorites if isinstance(value, str)))
    if owner_id and cleaned:
        connection.execute(
            table.insert(),
            [{"user_id": owner_id, "team_slug": slug, "position": position} for position, slug in enumerate(cleaned)],
        )
    connection.execute(sa.text("DELETE FROM app_settings WHERE key = 'live_team_favorites'"))


def downgrade() -> None:
    op.drop_table("user_team_favorites")
