"""
Notification Model

Database model for user notifications.
"""

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class NotificationType(str, enum.Enum):
    """Notification types"""
    TAX_RATE_UPDATE = "tax_rate_update"
    TAX_DEADLINE = "tax_deadline"
    REPORT_READY = "report_ready"
    SYSTEM_ANNOUNCEMENT = "system_announcement"


class Notification(Base):
    """User notification model"""
    
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)  # German message
    message_en = Column(Text)  # English message
    message_zh = Column(Text)  # Chinese message
    data = Column(JSONB)  # Additional data
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="notifications")
