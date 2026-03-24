"""Loan installment model for principal and interest breakdown tracking."""
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class LoanInstallmentSource(str, Enum):
    """Origin of installment breakdown data."""

    ESTIMATED = "estimated"
    MANUAL = "manual"
    BANK_STATEMENT = "bank_statement"
    ZINSBESCHEINIGUNG = "zinsbescheinigung"


class LoanInstallmentStatus(str, Enum):
    """Lifecycle state of an installment row."""

    SCHEDULED = "scheduled"
    POSTED = "posted"
    RECONCILED = "reconciled"
    OVERRIDDEN = "overridden"


class LoanInstallment(Base):
    """Canonical monthly loan breakdown row."""

    __tablename__ = "loan_installments"

    id = Column(Integer, primary_key=True, index=True)
    loan_id = Column(
        Integer,
        ForeignKey("property_loans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    due_date = Column(Date, nullable=False, index=True)
    actual_payment_date = Column(Date, nullable=True)
    tax_year = Column(Integer, nullable=False, index=True)

    scheduled_payment = Column(Numeric(12, 2), nullable=False)
    principal_amount = Column(Numeric(12, 2), nullable=False)
    interest_amount = Column(Numeric(12, 2), nullable=False)
    remaining_balance_after = Column(Numeric(12, 2), nullable=False)

    source = Column(
        SQLEnum(
            LoanInstallmentSource,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        default=LoanInstallmentSource.ESTIMATED,
    )
    status = Column(
        SQLEnum(
            LoanInstallmentStatus,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        default=LoanInstallmentStatus.SCHEDULED,
    )

    source_document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notes = Column(String(1000), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint("loan_id", "due_date", name="uq_loan_installments_loan_due_date"),
        CheckConstraint("scheduled_payment > 0", name="check_installment_payment_positive"),
        CheckConstraint("principal_amount >= 0", name="check_installment_principal_non_negative"),
        CheckConstraint("interest_amount >= 0", name="check_installment_interest_non_negative"),
        CheckConstraint(
            "remaining_balance_after >= 0",
            name="check_installment_remaining_balance_non_negative",
        ),
    )

    loan = relationship("PropertyLoan", back_populates="installments")
    source_document = relationship("Document")

    def __repr__(self):
        return (
            f"<LoanInstallment(id={self.id}, loan_id={self.loan_id}, "
            f"due_date={self.due_date}, payment={self.scheduled_payment})>"
        )
