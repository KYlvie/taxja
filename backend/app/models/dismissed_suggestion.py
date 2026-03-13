"""Model for tracking dismissed recurring transaction suggestions"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from app.db.base import Base


class DismissedSuggestion(Base):
    """Tracks dismissed recurring suggestions so they aren't re-shown"""

    __tablename__ = "dismissed_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(String(500), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    dismissed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
