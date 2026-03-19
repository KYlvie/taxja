"""CreditBalance model for user credit tracking"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, Boolean, DateTime, ForeignKey, CheckConstraint,
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class CreditBalance(Base):
    """User credit balance model (one-to-one with User)"""
    __tablename__ = "credit_balances"

    __table_args__ = (
        CheckConstraint("plan_balance >= 0", name="ck_credit_balances_plan_balance_non_negative"),
        CheckConstraint("topup_balance >= 0", name="ck_credit_balances_topup_balance_non_negative"),
        CheckConstraint(
            "overage_credits_used >= 0",
            name="ck_credit_balances_overage_credits_used_non_negative",
        ),
        CheckConstraint(
            "unpaid_overage_periods >= 0",
            name="ck_credit_balances_unpaid_overage_periods_non_negative",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    plan_balance = Column(Integer, nullable=False, default=0)
    topup_balance = Column(Integer, nullable=False, default=0)
    overage_enabled = Column(Boolean, nullable=False, default=False)
    overage_credits_used = Column(Integer, nullable=False, default=0)
    has_unpaid_overage = Column(Boolean, nullable=False, default=False)
    unpaid_overage_periods = Column(Integer, nullable=False, default=0)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="credit_balance")

    def __repr__(self):
        return (
            f"<CreditBalance(user_id={self.user_id}, "
            f"plan={self.plan_balance}, topup={self.topup_balance})>"
        )
