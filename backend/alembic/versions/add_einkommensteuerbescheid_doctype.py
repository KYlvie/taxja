"""Add EINKOMMENSTEUERBESCHEID to documenttype enum

Revision ID: add_bescheid_doctype
Revises: add_document_archival
Create Date: 2026-03-06
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'add_bescheid_doctype'
down_revision = 'add_document_archival'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The initial migration created the PG enum with UPPERCASE names (e.g. 'PAYSLIP'),
    # but SQLAlchemy's Enum(PythonEnum) sends .value which is lowercase (e.g. 'payslip').
    # Depending on how the DB was initialized (alembic vs create_all), the existing
    # values may be uppercase or lowercase. Add both to be safe.
    op.execute("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'EINKOMMENSTEUERBESCHEID'")
    op.execute("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'einkommensteuerbescheid'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # A full enum recreation would be needed, which is risky.
    # This downgrade is intentionally a no-op.
    pass
