"""Add asset tax engine foundation tables

Revision ID: 049_asset_tax_engine_foundation
Revises: 048_add_file_hash_to_documents
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "049_asset_tax_engine_foundation"
down_revision = "048_add_file_hash_to_documents"
branch_labels = None
depends_on = None


asset_event_type = sa.Enum(
    "acquired",
    "put_into_use",
    "reclassified",
    "business_use_changed",
    "degressive_to_linear_switch",
    "ifb_flagged",
    "ifb_claimed",
    "sold",
    "scrapped",
    "private_withdrawal",
    name="asseteventtype",
)

asset_event_trigger_source = sa.Enum(
    "system",
    "user",
    "policy_recompute",
    "import",
    name="asseteventtriggersource",
)


def upgrade() -> None:
    asset_event_type.create(op.get_bind(), checkfirst=True)
    asset_event_trigger_source.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "asset_policy_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("jurisdiction", sa.String(length=10), nullable=False),
        sa.Column("effective_anchor_date", sa.Date(), nullable=False),
        sa.Column("snapshot_payload", sa.JSON(), nullable=False),
        sa.Column("rule_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_asset_policy_snapshots_id"), "asset_policy_snapshots", ["id"], unique=False)
    op.create_index(
        op.f("ix_asset_policy_snapshots_user_id"),
        "asset_policy_snapshots",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_policy_snapshots_property_id"),
        "asset_policy_snapshots",
        ["property_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_policy_snapshots_effective_anchor_date"),
        "asset_policy_snapshots",
        ["effective_anchor_date"],
        unique=False,
    )

    op.create_table(
        "asset_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", asset_event_type, nullable=False),
        sa.Column("trigger_source", asset_event_trigger_source, nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_asset_events_id"), "asset_events", ["id"], unique=False)
    op.create_index(op.f("ix_asset_events_user_id"), "asset_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_asset_events_property_id"), "asset_events", ["property_id"], unique=False)
    op.create_index(op.f("ix_asset_events_event_type"), "asset_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_asset_events_event_date"), "asset_events", ["event_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_asset_events_event_date"), table_name="asset_events")
    op.drop_index(op.f("ix_asset_events_event_type"), table_name="asset_events")
    op.drop_index(op.f("ix_asset_events_property_id"), table_name="asset_events")
    op.drop_index(op.f("ix_asset_events_user_id"), table_name="asset_events")
    op.drop_index(op.f("ix_asset_events_id"), table_name="asset_events")
    op.drop_table("asset_events")

    op.drop_index(
        op.f("ix_asset_policy_snapshots_effective_anchor_date"),
        table_name="asset_policy_snapshots",
    )
    op.drop_index(op.f("ix_asset_policy_snapshots_property_id"), table_name="asset_policy_snapshots")
    op.drop_index(op.f("ix_asset_policy_snapshots_user_id"), table_name="asset_policy_snapshots")
    op.drop_index(op.f("ix_asset_policy_snapshots_id"), table_name="asset_policy_snapshots")
    op.drop_table("asset_policy_snapshots")

    asset_event_trigger_source.drop(op.get_bind(), checkfirst=True)
    asset_event_type.drop(op.get_bind(), checkfirst=True)
