#!/usr/bin/env python3
"""
Generate docker/init-db/init.sql from SQLAlchemy models.

Uses metadata.create_all with a recording engine to capture the exact
DDL that PostgreSQL would execute, then appends seed data INSERTs.

Usage:  python scripts/generate_init_sql.py
"""
import sys, os
from pathlib import Path
from io import StringIO
from datetime import datetime

BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

os.environ.setdefault("DATABASE_URL", "postgresql://x:x@localhost/x")
os.environ.setdefault("SECRET_KEY", "generate-init-sql-dummy-key-1234567890")
os.environ.setdefault("ENCRYPTION_KEY", "0" * 64)

from sqlalchemy import create_engine, event, text as sa_text
from sqlalchemy.dialects import postgresql as pg_dialect

from app.db.base import Base
# Import every model so metadata is fully populated
import app.models.user
import app.models.transaction
import app.models.document
import app.models.chat_message
import app.models.tax_report
import app.models.tax_configuration
import app.models.classification_correction
import app.models.loss_carryforward
import app.models.property
import app.models.property_loan
import app.models.recurring_transaction
import app.models.user_classification_rule
import app.models.transaction_line_item
import app.models.historical_import
import app.models.audit_log
import app.models.plan
import app.models.subscription
import app.models.payment_event
import app.models.usage_record
import app.models.notification
import app.models.dismissed_suggestion
import app.models.account_deletion_log
import app.models.disclaimer_acceptance
import app.models.tax_form_template
import app.models.tax_filing_data
import app.models.employer_month
import app.models.employer_annual_archive
import app.models.asset_event
import app.models.asset_policy_snapshot
import app.models.credit_balance
import app.models.credit_cost_config
import app.models.credit_ledger
import app.models.credit_topup_package
import app.models.topup_purchase
import app.models.user_deductibility_rule
import app.models.loan_installment
import app.models.liability
import app.models.reminder_state
import app.models.bank_statement_import

OUTPUT = Path(__file__).parent.parent / "docker" / "init-db" / "init.sql"
LATEST_MIGRATION = "073_add_document_year_fields"


def capture_ddl() -> str:
    """Use a mock PostgreSQL engine to capture all DDL statements."""
    statements = []

    def dump(sql, *multiparams, **params):
        compiled = sql.compile(dialect=engine.dialect)
        text = str(compiled).strip()
        if text:
            statements.append(text + ";")

    engine = create_engine("postgresql://", strategy="mock", executor=dump)
    Base.metadata.create_all(engine, checkfirst=False)
    return "\n\n".join(statements)


SEED_SQL = """
-- Plans (Free, Plus, Pro)
INSERT INTO plans (plan_type, name, monthly_price, yearly_price, features, quotas, monthly_credits, overage_price_per_credit, created_at, updated_at)
VALUES
  ('free', 'Free', 0.00, 0.00,
   '{"ai_assistant": true, "ocr_scanning": true, "basic_tax_calc": true, "multi_language": true, "transaction_entry": true}',
   '{}', 100, NULL, NOW(), NOW()),
  ('plus', 'Plus', 4.90, 49.00,
   '{"svs_calc": true, "vat_calc": true, "bank_import": true, "ai_assistant": true, "ocr_scanning": true, "full_tax_calc": true, "basic_tax_calc": true, "multi_language": true, "transaction_entry": true, "property_management": true, "recurring_suggestions": true, "unlimited_transactions": true}',
   '{}', 500, 0.0400, NOW(), NOW()),
  ('pro', 'Pro', 12.90, 129.00,
   '{"svs_calc": true, "vat_calc": true, "api_access": true, "bank_import": true, "ai_assistant": true, "ocr_scanning": true, "e1_generation": true, "full_tax_calc": true, "unlimited_ocr": true, "basic_tax_calc": true, "multi_language": true, "advanced_reports": true, "priority_support": true, "transaction_entry": true, "property_management": true, "recurring_suggestions": true, "unlimited_transactions": true}',
   '{}', 2000, 0.0300, NOW(), NOW())
ON CONFLICT DO NOTHING;

-- Credit cost configs
INSERT INTO credit_cost_configs (operation, credit_cost, description, pricing_version, is_active, updated_at)
VALUES
  ('ocr_scan', 5, 'OCR document scan', 1, true, NOW()),
  ('ai_conversation', 3, 'AI assistant conversation', 1, true, NOW()),
  ('transaction_entry', 1, 'Transaction entry', 1, true, NOW()),
  ('bank_import', 10, 'Bank statement import', 1, true, NOW()),
  ('e1_generation', 20, 'E1 tax form generation', 1, true, NOW()),
  ('tax_calc', 2, 'Tax calculation', 1, true, NOW())
ON CONFLICT DO NOTHING;

-- Credit topup packages
INSERT INTO credit_topup_packages (name, credits, price, is_active, created_at)
VALUES
  ('Small Pack', 100, 4.99, true, NOW()),
  ('Medium Pack', 300, 12.99, true, NOW()),
  ('Large Pack', 1000, 39.99, true, NOW())
ON CONFLICT DO NOTHING;

-- Tax configurations are seeded by the application on startup.
-- See backend/app/db/seed_tax_config.py
"""


def main():
    print("Generating init.sql from SQLAlchemy models...")

    ddl = capture_ddl()

    with OUTPUT.open("w", encoding="utf-8", newline="\n") as f:
        f.write("-- =============================================================\n")
        f.write("-- Taxja Database Initialization Script\n")
        f.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"-- Latest migration: {LATEST_MIGRATION}\n")
        f.write("-- =============================================================\n\n")
        f.write("SET statement_timeout = 0;\n")
        f.write("SET lock_timeout = 0;\n")
        f.write("SET client_encoding = 'UTF8';\n")
        f.write("SET standard_conforming_strings = on;\n")
        f.write("SET check_function_bodies = false;\n\n")

        f.write("-- =============================================================\n")
        f.write("-- PART 1: Schema (enums, tables, indexes, constraints)\n")
        f.write("-- =============================================================\n\n")
        f.write(ddl)

        f.write("\n\n-- =============================================================\n")
        f.write("-- PART 2: Seed Data\n")
        f.write("-- =============================================================\n")
        f.write(SEED_SQL)

        f.write("\n-- =============================================================\n")
        f.write("-- PART 3: Alembic version stamp\n")
        f.write("-- =============================================================\n\n")
        f.write("CREATE TABLE IF NOT EXISTS alembic_version (\n")
        f.write("    version_num VARCHAR(32) NOT NULL,\n")
        f.write("    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)\n")
        f.write(");\n\n")
        f.write(f"INSERT INTO alembic_version (version_num)\n")
        f.write(f"  VALUES ('{LATEST_MIGRATION}')\n")
        f.write(f"  ON CONFLICT DO NOTHING;\n")

    size = OUTPUT.stat().st_size
    print(f"OK: {OUTPUT} ({size:,} bytes)")


if __name__ == "__main__":
    main()
