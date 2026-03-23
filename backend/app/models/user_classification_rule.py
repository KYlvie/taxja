"""Per-user classification rules derived from corrections and preferences."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base


class UserClassificationRule(Base):
    """
    Per-user override rules for transaction classification.

    When a user corrects a classification, we store a rule mapping
    the full normalized description (not just merchant) to a category.
    This means "amazon druckerpatrone" and "amazon kleidung" are separate rules,
    because the same merchant can sell deductible and non-deductible items.
    """

    __tablename__ = "user_classification_rules"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "normalized_description", "txn_type",
            name="uq_user_description_type",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Normalized full description (lowered, noise stripped, but product keywords kept)
    normalized_description = Column(String(300), nullable=False, index=True)

    # Original raw description (for display in UI)
    original_description = Column(String(500), nullable=True)

    # Transaction type: "income" or "expense"
    txn_type = Column(String(20), nullable=False)

    # The user's preferred category
    category = Column(String(100), nullable=False)

    # How many times this rule was confirmed (corrections count)
    hit_count = Column(Integer, default=1, nullable=False)

    # Confidence — starts at 1.0 for explicit user corrections
    confidence = Column(Numeric(3, 2), default=1.00, nullable=False)

    # Rule type: "strict" (human-confirmed) or "soft" (LLM-inferred).
    # Strict rules are fully trusted; soft rules can be challenged by
    # downstream classifiers and carry reduced confidence.
    rule_type = Column(String(10), default="strict", nullable=False)

    # Lifecycle fields for rule hygiene
    last_hit_at = Column(DateTime, nullable=True)
    conflict_count = Column(Integer, default=0, nullable=False)
    frozen = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="classification_rules")

    def __repr__(self):
        return (
            f"<UserClassificationRule(user={self.user_id}, "
            f"desc={self.normalized_description!r}, "
            f"category={self.category})>"
        )
