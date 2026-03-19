"""CreditLedger model for credit transaction audit log"""
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey,
    CheckConstraint, Index, Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class CreditOperation(str, Enum):
    """Types of credit operations"""
    DEDUCTION = "deduction"
    REFUND = "refund"
    MONTHLY_RESET = "monthly_reset"
    TOPUP = "topup"
    TOPUP_EXPIRY = "topup_expiry"
    OVERAGE_SETTLEMENT = "overage_settlement"
    ADMIN_ADJUSTMENT = "admin_adjustment"
    MIGRATION = "migration"


class CreditSource(str, Enum):
    """Source of credit for the operation"""
    PLAN = "plan"
    TOPUP = "topup"
    OVERAGE = "overage"
    MIXED = "mixed"


class CreditLedgerStatus(str, Enum):
    """Status of a ledger entry"""
    SETTLED = "settled"      # v1 default
    RESERVED = "reserved"    # v2: reservation flow
    REVERSED = "reversed"    # v2: reversed reservation
    FAILED = "failed"        # abnormal: partial persist side-effects


class CreditLedger(Base):
    """Credit transaction audit log"""
    __tablename__ = "credit_ledger"

    __table_args__ = (
        CheckConstraint("credit_amount != 0", name="ck_credit_ledger_amount_nonzero"),
        CheckConstraint(
            "plan_balance_after >= 0",
            name="ck_credit_ledger_plan_balance_after_non_negative",
        ),
        CheckConstraint(
            "topup_balance_after >= 0",
            name="ck_credit_ledger_topup_balance_after_non_negative",
        ),
        CheckConstraint(
            "overage_portion >= 0",
            name="ck_credit_ledger_overage_portion_non_negative",
        ),
        # Composite indexes
        Index("ix_credit_ledger_user_created", "user_id", "created_at"),
        Index("ix_credit_ledger_user_operation", "user_id", "operation"),
        Index("ix_credit_ledger_context", "context_type", "context_id"),
        # Partial unique index: refund idempotency
        Index(
            "uq_credit_ledger_refund_key",
            "user_id",
            "reference_id",
            unique=True,
            postgresql_where="operation = 'refund' AND reference_id IS NOT NULL",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation = Column(
        SQLEnum(
            CreditOperation,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    operation_detail = Column(String(100), nullable=True)
    status = Column(
        SQLEnum(
            CreditLedgerStatus,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=CreditLedgerStatus.SETTLED,
        index=True,
    )
    credit_amount = Column(Integer, nullable=False)
    source = Column(
        SQLEnum(
            CreditSource,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=CreditSource.PLAN,
    )
    plan_balance_after = Column(Integer, nullable=False)
    topup_balance_after = Column(Integer, nullable=False)
    is_overage = Column(Boolean, nullable=False, default=False)
    overage_portion = Column(Integer, nullable=False, default=0)
    context_type = Column(String(50), nullable=True)
    context_id = Column(Integer, nullable=True)
    reference_id = Column(String(255), nullable=True)
    reservation_id = Column(String(255), nullable=True)  # v2 reservation link; v1 always null
    reason = Column(String(200), nullable=True)
    pricing_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="credit_ledger")

    def __repr__(self):
        return (
            f"<CreditLedger(id={self.id}, user_id={self.user_id}, "
            f"op={self.operation}, amount={self.credit_amount})>"
        )
