"""Sync PostgreSQL enum types with Python enum definitions.

Adds missing values to expensecategory, incomecategory, and transactiontype enums.
The DB stores enum *names* (uppercase), matching SQLAlchemy's default behavior.

Revision ID: 017
Revises: 016
Create Date: 2026-03-10
"""
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None

# expensecategory: DB has 15 values from 001. Missing 8 values.
MISSING_EXPENSE = [
    "VEHICLE",
    "TELECOM",
    "RENT",
    "BANK_FEES",
    "SVS_CONTRIBUTIONS",
    "PROPERTY_MANAGEMENT_FEES",
    "PROPERTY_INSURANCE",
    "DEPRECIATION_AFA",
]

# incomecategory: DB has 4 values from 001. Missing 3 values.
MISSING_INCOME = [
    "AGRICULTURE",
    "BUSINESS",
    "OTHER_INCOME",
]


def upgrade() -> None:
    for val in MISSING_EXPENSE:
        op.execute(f"ALTER TYPE expensecategory ADD VALUE IF NOT EXISTS '{val}'")
    for val in MISSING_INCOME:
        op.execute(f"ALTER TYPE incomecategory ADD VALUE IF NOT EXISTS '{val}'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    pass
