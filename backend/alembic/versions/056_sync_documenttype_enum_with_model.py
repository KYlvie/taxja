"""Sync documenttype enum values with current DocumentType model.

Revision ID: 056_sync_doctypes
Revises: 055_add_user_tax_profile_fields
Create Date: 2026-03-20
"""

from alembic import op


revision = "056_sync_doctypes"
down_revision = "055_add_user_tax_profile_fields"
branch_labels = None
depends_on = None


_DOCUMENTTYPE_VALUES = (
    "SPENDENBESTAETIGUNG",
    "VERSICHERUNGSBESTAETIGUNG",
    "KINDERBETREUUNGSKOSTEN",
    "FORTBILDUNGSKOSTEN",
    "PENDLERPAUSCHALE",
    "KIRCHENBEITRAG",
    "GRUNDBUCHAUSZUG",
    "BETRIEBSKOSTENABRECHNUNG",
    "GEWERBESCHEIN",
    "KONTOAUSZUG",
)


def upgrade() -> None:
    # Some environments were initialized with UPPERCASE enum names while
    # others persist lowercase enum values. Add both variants defensively.
    for value in _DOCUMENTTYPE_VALUES:
        op.execute(f"ALTER TYPE documenttype ADD VALUE IF NOT EXISTS '{value}'")
        op.execute(f"ALTER TYPE documenttype ADD VALUE IF NOT EXISTS '{value.lower()}'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely in place.
    # This migration is intentionally irreversible.
    pass
