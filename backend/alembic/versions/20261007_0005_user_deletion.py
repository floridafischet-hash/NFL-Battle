"""Allow users to be deleted while retaining immutable audit history.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-07 10:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # IF EXISTS also supports installations that briefly ran the original 0003 version of this
    # migration before the app-settings and superuser migrations were added upstream.
    op.execute("ALTER TABLE audit_logs DROP CONSTRAINT IF EXISTS fk_audit_logs_actor_user_id_users")


def downgrade() -> None:
    op.create_foreign_key(
        op.f("fk_audit_logs_actor_user_id_users"),
        "audit_logs",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
