"""Seed credit billing data: CreditBalance for existing users, CreditCostConfig,
CreditTopupPackage, and MIGRATION ledger entries.

Revision ID: 054
Revises: 053
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers
revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.utcnow().isoformat()

    # 1. Seed CreditCostConfig initial data
    cost_configs = [
        ("ocr_scan", 5, "OCR document scanning"),
        ("ai_conversation", 10, "AI assistant conversation"),
        ("transaction_entry", 1, "Manual transaction entry"),
        ("bank_import", 3, "Bank statement import"),
        ("e1_generation", 20, "E1 tax form generation"),
        ("tax_calc", 2, "Tax calculation"),
    ]
    for operation, cost, description in cost_configs:
        conn.execute(
            sa.text(
                "INSERT INTO credit_cost_configs (operation, credit_cost, description, "
                "pricing_version, is_active) "
                "VALUES (:op, :cost, :desc, 1, true) "
                "ON CONFLICT (operation) DO NOTHING"
            ),
            {"op": operation, "cost": cost, "desc": description},
        )

    # 2. Seed CreditTopupPackage initial data
    packages = [
        ("Small Pack", 100, 4.99),
        ("Medium Pack", 300, 12.99),
        ("Large Pack", 1000, 39.99),
    ]
    for name, credits, price in packages:
        conn.execute(
            sa.text(
                "INSERT INTO credit_topup_packages (name, credits, price, is_active) "
                "VALUES (:name, :credits, :price, true) "
                "ON CONFLICT DO NOTHING"
            ),
            {"name": name, "credits": credits, "price": price},
        )

    # 3. Create CreditBalance for all existing users who don't have one
    conn.execute(
        sa.text(
            """
            INSERT INTO credit_balances (user_id, plan_balance, topup_balance,
                overage_enabled, overage_credits_used, has_unpaid_overage,
                unpaid_overage_periods)
            SELECT u.id,
                   COALESCE(p.monthly_credits, 0),
                   0,
                   false,
                   0,
                   false,
                   0
            FROM users u
            LEFT JOIN subscriptions s ON s.user_id = u.id
            LEFT JOIN plans p ON p.id = s.plan_id
            WHERE u.id NOT IN (SELECT user_id FROM credit_balances)
            """
        )
    )

    # 4. Write MIGRATION ledger entries for newly created balances
    conn.execute(
        sa.text(
            """
            INSERT INTO credit_ledger (user_id, operation, operation_detail, status,
                credit_amount, source, plan_balance_after, topup_balance_after,
                is_overage, overage_portion, reason, pricing_version, created_at)
            SELECT cb.user_id,
                   'migration',
                   'migration',
                   'settled',
                   cb.plan_balance,
                   'plan',
                   cb.plan_balance,
                   0,
                   false,
                   0,
                   'Initial credit migration from quota-based billing',
                   1,
                   :now
            FROM credit_balances cb
            WHERE cb.user_id NOT IN (
                SELECT user_id FROM credit_ledger
                WHERE operation = 'migration'
            )
            """
        ),
        {"now": now},
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove migration ledger entries
    conn.execute(
        sa.text("DELETE FROM credit_ledger WHERE operation = 'migration'")
    )

    # Remove seeded CreditBalance records (all of them since they were auto-created)
    # Note: keeping this conservative — only remove if no other ledger entries exist
    conn.execute(
        sa.text(
            """
            DELETE FROM credit_balances
            WHERE user_id NOT IN (
                SELECT DISTINCT user_id FROM credit_ledger
                WHERE operation != 'migration'
            )
            """
        )
    )

    # Remove seeded packages and cost configs
    conn.execute(sa.text("DELETE FROM credit_topup_packages"))
    conn.execute(sa.text("DELETE FROM credit_cost_configs"))
