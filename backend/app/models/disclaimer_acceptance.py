"""
Disclaimer Acceptance Model

Tracks user acceptance of legal disclaimers.

Requirements: 17.11
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import Base


class DisclaimerAcceptance(Base):
    """Disclaimer acceptance record"""
    
    __tablename__ = "disclaimer_acceptances"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(20), nullable=False)
    language = Column(String(5), nullable=False)
    accepted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ip_address = Column(String(45), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="disclaimer_acceptances")
    
    def __repr__(self):
        return f"<DisclaimerAcceptance(user_id={self.user_id}, version={self.version}, accepted_at={self.accepted_at})>"
