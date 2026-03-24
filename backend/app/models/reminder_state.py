"""Persistent state for non-document proactive reminders."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class ReminderState(Base):
    """Stores snooze/resolve lifecycle for proactive reminders."""

    __tablename__ = "reminder_states"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "reminder_kind",
            "fingerprint",
            name="uq_reminder_state_user_kind_fingerprint",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reminder_kind = Column(String(80), nullable=False, index=True)
    bucket = Column(String(40), nullable=False)
    fingerprint = Column(String(128), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    snoozed_until = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="reminder_states")

    def __repr__(self) -> str:
        return (
            f"<ReminderState(user_id={self.user_id}, kind={self.reminder_kind}, "
            f"status={self.status}, fingerprint={self.fingerprint[:10]}...)>"
        )
