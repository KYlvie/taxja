"""Transaction line item model for canonical posting lines within a transaction.

A single transaction (e.g. one supermarket receipt or one loan installment)
can contain multiple posting lines with different tax and bookkeeping semantics.
Line items allow:
- Per-item classification (office_supplies vs groceries on one Billa receipt)
- Deductible vs private-use allocation on the same cash event
- Liability and asset movements that must not be treated as expenses
- Accurate report aggregation independent of the parent transaction type
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, DateTime,
    ForeignKey, Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class LineItemPostingType(str, Enum):
    """Canonical posting semantic for a line item."""

    INCOME = "income"
    EXPENSE = "expense"
    PRIVATE_USE = "private_use"
    ASSET_ACQUISITION = "asset_acquisition"
    LIABILITY_DRAWDOWN = "liability_drawdown"
    LIABILITY_REPAYMENT = "liability_repayment"
    TAX_PAYMENT = "tax_payment"
    TRANSFER = "transfer"


class LineItemAllocationSource(str, Enum):
    """How a line item's allocation was produced."""

    MANUAL = "manual"
    OCR_SPLIT = "ocr_split"
    PERCENTAGE_RULE = "percentage_rule"
    CAP_RULE = "cap_rule"
    LOAN_INSTALLMENT = "loan_installment"
    MIXED_USE_RULE = "mixed_use_rule"
    VAT_POLICY = "vat_policy"
    LEGACY_BACKFILL = "legacy_backfill"


LINE_ITEM_POSTING_TYPE_ENUM = SQLEnum(
    LineItemPostingType,
    name="lineitempostingtype",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
    validate_strings=True,
)

LINE_ITEM_ALLOCATION_SOURCE_ENUM = SQLEnum(
    LineItemAllocationSource,
    name="lineitemallocationsource",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
    validate_strings=True,
)


class TransactionLineItem(Base):
    """Individual item within a transaction."""

    __tablename__ = "transaction_line_items"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(
        Integer, ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Item description (e.g. "Druckerpapier A4", "Milch 1L")
    description = Column(String(500), nullable=False)

    # Item amount (positive)
    amount = Column(Numeric(12, 2), nullable=False)

    # Quantity (default 1)
    quantity = Column(Integer, default=1, nullable=False)

    # Canonical posting semantics for this line
    posting_type = Column(
        LINE_ITEM_POSTING_TYPE_ENUM,
        nullable=False,
        default=LineItemPostingType.EXPENSE,
    )
    allocation_source = Column(
        LINE_ITEM_ALLOCATION_SOURCE_ENUM,
        nullable=False,
        default=LineItemAllocationSource.MANUAL,
    )

    # Category for this specific item
    category = Column(String(100), nullable=True)

    # Deductibility at item level
    is_deductible = Column(Boolean, default=False, nullable=False)
    deduction_reason = Column(String(500), nullable=True)

    # VAT for this item (can differ per item, e.g. 10% vs 20%)
    vat_rate = Column(Numeric(5, 4), nullable=True)
    vat_amount = Column(Numeric(12, 2), nullable=True)
    vat_recoverable_amount = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Recalculation bucket for yearly caps / shared allocation rules
    rule_bucket = Column(String(100), nullable=True)

    # Classification method and confidence at item level
    classification_method = Column(String(20), nullable=True)
    classification_confidence = Column(Numeric(3, 2), nullable=True)

    # Sort order within the transaction
    sort_order = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
    )

    # Relationships
    transaction = relationship("Transaction", back_populates="line_items")

    def __repr__(self):
        return (
            f"<TransactionLineItem(id={self.id}, "
            f"desc={self.description!r}, "
            f"posting_type={self.posting_type}, "
            f"amount={self.amount}, "
            f"deductible={self.is_deductible})>"
        )
