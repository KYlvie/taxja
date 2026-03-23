"""add reminder states table

Revision ID: 065_add_reminder_states_table
Revises: 064_add_asset_disposal_fields
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "065_add_reminder_states_table"
down_revision = "064_add_asset_disposal_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reminder_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("reminder_kind", sa.String(length=80), nullable=False),
        sa.Column("bucket", sa.String(length=40), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("snoozed_until", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "reminder_kind",
            "fingerprint",
            name="uq_reminder_state_user_kind_fingerprint",
        ),
    )
    op.create_index(op.f("ix_reminder_states_id"), "reminder_states", ["id"], unique=False)
    op.create_index(op.f("ix_reminder_states_user_id"), "reminder_states", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_reminder_states_reminder_kind"),
        "reminder_states",
        ["reminder_kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reminder_states_fingerprint"),
        "reminder_states",
        ["fingerprint"],
        unique=False,
    )
    op.create_index(op.f("ix_reminder_states_status"), "reminder_states", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reminder_states_status"), table_name="reminder_states")
    op.drop_index(op.f("ix_reminder_states_fingerprint"), table_name="reminder_states")
    op.drop_index(op.f("ix_reminder_states_reminder_kind"), table_name="reminder_states")
    op.drop_index(op.f("ix_reminder_states_user_id"), table_name="reminder_states")
    op.drop_index(op.f("ix_reminder_states_id"), table_name="reminder_states")
    op.drop_table("reminder_states")
