"""Add source column to classification_corrections for tiered learning.

Revision ID: 040
Revises: 039_user_rules_line_items
Create Date: 2026-03-16

Supports the tiered write strategy:
- human_verified: explicit user corrections (safe for ML retraining)
- llm_verified: high-confidence LLM results >= 0.85 (safe for ML retraining)
- llm_unverified: medium-confidence LLM results 0.60-0.85 (audit only)
- system_default: system-generated defaults
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "040"
down_revision = "039_user_rules_line_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "classification_corrections",
        sa.Column("source", sa.String(30), nullable=True, server_default="human_verified"),
    )
    # Back-fill existing rows as human_verified (they predate tiered logic)
    op.execute(
        "UPDATE classification_corrections SET source = 'human_verified' WHERE source IS NULL"
    )


def downgrade() -> None:
    op.drop_column("classification_corrections", "source")
