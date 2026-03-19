"""Transaction line item model for per-item classification within a transaction.

A single transaction (e.g. one supermarket receipt) can contain multiple items
with different tax categories and deductibility. Line items allow:
- Per-item classification (office_supplies vs groceries on one Billa receipt)
- Per-item deductibility (printer paper = deductible, milk = not)
- Accurate tax reporting by category instead of whole-transaction amounts
- User editing of individual item classifications
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, DateTime,
    ForeignKey, Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from app.db.base import Base


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

    # Category for this specific item
    category = Column(String(100), nullable=True)

    # Deductibility at item level
    is_deductible = Column(Boolean, default=False, nullable=False)
    deduction_reason = Column(String(500), nullable=True)

    # VAT for this item (can differ per item, e.g. 10% vs 20%)
    vat_rate = Column(Numeric(5, 4), nullable=True)
    vat_amount = Column(Numeric(12, 2), nullable=True)

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
            f"amount={self.amount}, "
            f"deductible={self.is_deductible})>"
        )
