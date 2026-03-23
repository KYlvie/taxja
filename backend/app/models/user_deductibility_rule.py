"""Per-user deductibility override rules derived from human corrections."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class UserDeductibilityRule(Base):
    """Persist user-confirmed deductible / non-deductible judgments."""

    __tablename__ = "user_deductibility_rules"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "normalized_description",
            "expense_category",
            name="uq_user_deductibility_description_category",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    normalized_description = Column(String(300), nullable=False, index=True)
    original_description = Column(String(500), nullable=True)
    expense_category = Column(String(100), nullable=False, index=True)
    is_deductible = Column(Boolean, nullable=False, default=False)
    reason = Column(String(500), nullable=True)
    hit_count = Column(Integer, default=1, nullable=False)
    last_hit_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="deductibility_rules")

    def __repr__(self):
        return (
            f"<UserDeductibilityRule(user={self.user_id}, "
            f"desc={self.normalized_description!r}, "
            f"category={self.expense_category}, "
            f"deductible={self.is_deductible})>"
        )
