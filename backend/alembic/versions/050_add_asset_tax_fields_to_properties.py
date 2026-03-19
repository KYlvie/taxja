"""Add persisted asset tax fields to properties

Revision ID: 050_add_asset_tax_fields_to_properties
Revises: 049_asset_tax_engine_foundation
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa


revision = "050_add_asset_tax_fields_to_properties"
down_revision = "049_asset_tax_engine_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("acquisition_kind", sa.String(length=30), nullable=True))
    op.add_column("properties", sa.Column("put_into_use_date", sa.Date(), nullable=True))
    op.add_column("properties", sa.Column("is_used_asset", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("properties", sa.Column("first_registration_date", sa.Date(), nullable=True))
    op.add_column("properties", sa.Column("prior_owner_usage_years", sa.Numeric(5, 2), nullable=True))
    op.add_column("properties", sa.Column("comparison_basis", sa.String(length=10), nullable=True))
    op.add_column("properties", sa.Column("comparison_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("properties", sa.Column("gwg_eligible", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("properties", sa.Column("gwg_elected", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("properties", sa.Column("depreciation_method", sa.String(length=20), nullable=True, server_default="linear"))
    op.add_column("properties", sa.Column("degressive_afa_rate", sa.Numeric(5, 4), nullable=True))
    op.add_column("properties", sa.Column("useful_life_source", sa.String(length=50), nullable=True))
    op.add_column("properties", sa.Column("income_tax_cost_cap", sa.Numeric(12, 2), nullable=True))
    op.add_column("properties", sa.Column("income_tax_depreciable_base", sa.Numeric(12, 2), nullable=True))
    op.add_column("properties", sa.Column("vat_recoverable_status", sa.String(length=20), nullable=True))
    op.add_column("properties", sa.Column("ifb_candidate", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("properties", sa.Column("ifb_rate", sa.Numeric(5, 4), nullable=True))
    op.add_column("properties", sa.Column("ifb_rate_source", sa.String(length=50), nullable=True))
    op.add_column("properties", sa.Column("recognition_decision", sa.String(length=50), nullable=True))
    op.add_column("properties", sa.Column("policy_confidence", sa.Numeric(5, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "policy_confidence")
    op.drop_column("properties", "recognition_decision")
    op.drop_column("properties", "ifb_rate_source")
    op.drop_column("properties", "ifb_rate")
    op.drop_column("properties", "ifb_candidate")
    op.drop_column("properties", "vat_recoverable_status")
    op.drop_column("properties", "income_tax_depreciable_base")
    op.drop_column("properties", "income_tax_cost_cap")
    op.drop_column("properties", "useful_life_source")
    op.drop_column("properties", "degressive_afa_rate")
    op.drop_column("properties", "depreciation_method")
    op.drop_column("properties", "gwg_elected")
    op.drop_column("properties", "gwg_eligible")
    op.drop_column("properties", "comparison_amount")
    op.drop_column("properties", "comparison_basis")
    op.drop_column("properties", "prior_owner_usage_years")
    op.drop_column("properties", "first_registration_date")
    op.drop_column("properties", "is_used_asset")
    op.drop_column("properties", "put_into_use_date")
    op.drop_column("properties", "acquisition_kind")
