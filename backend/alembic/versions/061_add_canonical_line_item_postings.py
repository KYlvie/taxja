"""Add canonical posting metadata to transaction line items.

Revision ID: 061_canonical_line_items
Revises: 060_add_loan_installments
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "061_canonical_line_items"
down_revision = "060_add_loan_installments"
branch_labels = None
depends_on = None


BATCH_SIZE = 1000

posting_type_enum = postgresql.ENUM(
    "income",
    "expense",
    "private_use",
    "asset_acquisition",
    "liability_drawdown",
    "liability_repayment",
    "tax_payment",
    "transfer",
    name="lineitempostingtype",
    create_type=False,
)

allocation_source_enum = postgresql.ENUM(
    "manual",
    "ocr_split",
    "percentage_rule",
    "cap_rule",
    "loan_installment",
    "mixed_use_rule",
    "vat_policy",
    "legacy_backfill",
    name="lineitemallocationsource",
    create_type=False,
)


def _enum_literal(bind, enum_name: str, value: str) -> str:
    if bind.dialect.name == "postgresql":
        return f"'{value}'::{enum_name}"
    return f"'{value}'"


def _backfill_existing_line_items(bind) -> None:
    tt = lambda v: f"'{v}'::transactiontype" if bind.dialect.name == "postgresql" else f"'{v}'"
    posting_case = f"""
        CASE t.type
            WHEN {tt('income')} THEN {_enum_literal(bind, 'lineitempostingtype', 'income')}
            WHEN {tt('asset_acquisition')} THEN {_enum_literal(bind, 'lineitempostingtype', 'asset_acquisition')}
            WHEN {tt('liability_drawdown')} THEN {_enum_literal(bind, 'lineitempostingtype', 'liability_drawdown')}
            WHEN {tt('liability_repayment')} THEN {_enum_literal(bind, 'lineitempostingtype', 'liability_repayment')}
            WHEN {tt('tax_payment')} THEN {_enum_literal(bind, 'lineitempostingtype', 'tax_payment')}
            WHEN {tt('transfer')} THEN {_enum_literal(bind, 'lineitempostingtype', 'transfer')}
            ELSE {_enum_literal(bind, 'lineitempostingtype', 'expense')}
        END
    """
    category_case = f"""
        CASE
            WHEN t.type = {tt('income')} THEN CAST(t.income_category AS VARCHAR)
            WHEN t.type = {tt('expense')} THEN CAST(t.expense_category AS VARCHAR)
            ELSE NULL
        END
    """
    update_sql = sa.text(
        f"""
        UPDATE transaction_line_items AS li
        SET
            posting_type = COALESCE(li.posting_type, {posting_case}),
            allocation_source = COALESCE(
                li.allocation_source,
                {_enum_literal(bind, 'lineitemallocationsource', 'legacy_backfill')}
            ),
            category = COALESCE(li.category, {category_case}),
            vat_recoverable_amount = COALESCE(li.vat_recoverable_amount, 0),
            rule_bucket = COALESCE(li.rule_bucket, NULL)
        FROM transactions AS t
        WHERE li.transaction_id = t.id
        """
    )
    bind.execute(update_sql)


def _insert_missing_mirror_lines(bind) -> None:
    tt = lambda v: f"'{v}'::transactiontype" if bind.dialect.name == "postgresql" else f"'{v}'"
    last_id = 0
    while True:
        insert_sql = sa.text(
            f"""
            WITH missing AS (
                SELECT
                    t.id,
                    t.type,
                    t.amount,
                    t.description,
                    t.income_category,
                    t.expense_category,
                    t.is_deductible,
                    t.deduction_reason,
                    t.vat_rate,
                    t.vat_amount,
                    t.classification_method
                FROM transactions AS t
                LEFT JOIN transaction_line_items AS li
                    ON li.transaction_id = t.id
                WHERE li.id IS NULL
                  AND t.id > :last_id
                ORDER BY t.id ASC
                LIMIT :batch_size
            )
            INSERT INTO transaction_line_items (
                transaction_id,
                description,
                amount,
                quantity,
                posting_type,
                allocation_source,
                category,
                is_deductible,
                deduction_reason,
                vat_rate,
                vat_amount,
                vat_recoverable_amount,
                rule_bucket,
                classification_method,
                sort_order,
                created_at,
                updated_at
            )
            SELECT
                m.id,
                COALESCE(m.description, 'Transaction'),
                m.amount,
                1,
                CASE m.type
                    WHEN {tt('income')} THEN {_enum_literal(bind, 'lineitempostingtype', 'income')}
                    WHEN {tt('asset_acquisition')} THEN {_enum_literal(bind, 'lineitempostingtype', 'asset_acquisition')}
                    WHEN {tt('liability_drawdown')} THEN {_enum_literal(bind, 'lineitempostingtype', 'liability_drawdown')}
                    WHEN {tt('liability_repayment')} THEN {_enum_literal(bind, 'lineitempostingtype', 'liability_repayment')}
                    WHEN {tt('tax_payment')} THEN {_enum_literal(bind, 'lineitempostingtype', 'tax_payment')}
                    WHEN {tt('transfer')} THEN {_enum_literal(bind, 'lineitempostingtype', 'transfer')}
                    ELSE {_enum_literal(bind, 'lineitempostingtype', 'expense')}
                END,
                {_enum_literal(bind, 'lineitemallocationsource', 'legacy_backfill')},
                CASE
                    WHEN m.type = {tt('income')} THEN CAST(m.income_category AS VARCHAR)
                    WHEN m.type = {tt('expense')} THEN CAST(m.expense_category AS VARCHAR)
                    ELSE NULL
                END,
                CASE
                    WHEN m.type = {tt('expense')} THEN COALESCE(m.is_deductible, false)
                    ELSE false
                END,
                CASE
                    WHEN m.type = {tt('expense')} THEN m.deduction_reason
                    ELSE NULL
                END,
                m.vat_rate,
                m.vat_amount,
                0,
                NULL,
                m.classification_method,
                0,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM missing AS m
            RETURNING transaction_id
            """
        )
        inserted_ids = [row[0] for row in bind.execute(insert_sql, {"last_id": last_id, "batch_size": BATCH_SIZE})]
        if not inserted_ids:
            break
        last_id = max(inserted_ids)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        posting_type_enum.create(bind, checkfirst=True)
        allocation_source_enum.create(bind, checkfirst=True)

    op.add_column(
        "transaction_line_items",
        sa.Column("posting_type", posting_type_enum if bind.dialect.name == "postgresql" else sa.String(length=50), nullable=True),
    )
    op.add_column(
        "transaction_line_items",
        sa.Column("allocation_source", allocation_source_enum if bind.dialect.name == "postgresql" else sa.String(length=50), nullable=True),
    )
    op.add_column(
        "transaction_line_items",
        sa.Column("vat_recoverable_amount", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "transaction_line_items",
        sa.Column("rule_bucket", sa.String(length=100), nullable=True),
    )

    with op.get_context().autocommit_block():
        _backfill_existing_line_items(bind)
        _insert_missing_mirror_lines(bind)

    op.alter_column(
        "transaction_line_items",
        "posting_type",
        existing_type=posting_type_enum if bind.dialect.name == "postgresql" else sa.String(length=50),
        nullable=False,
        server_default=sa.text("'expense'"),
    )
    op.alter_column(
        "transaction_line_items",
        "allocation_source",
        existing_type=allocation_source_enum if bind.dialect.name == "postgresql" else sa.String(length=50),
        nullable=False,
        server_default=sa.text("'manual'"),
    )
    op.alter_column(
        "transaction_line_items",
        "vat_recoverable_amount",
        existing_type=sa.Numeric(12, 2),
        nullable=False,
        server_default=sa.text("0"),
    )


def downgrade() -> None:
    op.drop_column("transaction_line_items", "rule_bucket")
    op.drop_column("transaction_line_items", "vat_recoverable_amount")
    op.drop_column("transaction_line_items", "allocation_source")
    op.drop_column("transaction_line_items", "posting_type")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        allocation_source_enum.drop(bind, checkfirst=True)
        posting_type_enum.drop(bind, checkfirst=True)
