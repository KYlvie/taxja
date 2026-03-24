"""Resync documenttype enum values with the current DocumentType model.

Revision ID: 068_resync_doctypes
Revises: 067_bank_statement_workbench
Create Date: 2026-03-23 23:45:00.000000
"""

from alembic import op


revision = "068_resync_doctypes"
down_revision = "067_bank_statement_workbench"
branch_labels = None
depends_on = None


_DOCUMENTTYPE_VALUES = (
    "PAYSLIP",
    "RECEIPT",
    "INVOICE",
    "PURCHASE_CONTRACT",
    "RENTAL_CONTRACT",
    "LOAN_CONTRACT",
    "BANK_STATEMENT",
    "PROPERTY_TAX",
    "LOHNZETTEL",
    "SVS_NOTICE",
    "EINKOMMENSTEUERBESCHEID",
    "E1_FORM",
    "L1_FORM",
    "L1K_BEILAGE",
    "L1AB_BEILAGE",
    "E1A_BEILAGE",
    "E1B_BEILAGE",
    "E1KV_BEILAGE",
    "U1_FORM",
    "U30_FORM",
    "JAHRESABSCHLUSS",
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
    "OTHER",
)


def upgrade() -> None:
    # Environments are inconsistent: some were initialized with uppercase enum
    # labels while others persist lowercase string values. Add both variants so
    # document review can safely write every current DocumentType.
    for value in _DOCUMENTTYPE_VALUES:
        op.execute(f"ALTER TYPE documenttype ADD VALUE IF NOT EXISTS '{value}'")
        op.execute(f"ALTER TYPE documenttype ADD VALUE IF NOT EXISTS '{value.lower()}'")


def downgrade() -> None:
    # PostgreSQL enum labels cannot be removed safely in place.
    pass
