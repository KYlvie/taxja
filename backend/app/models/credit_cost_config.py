"""CreditCostConfig model for global operation credit cost configuration"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.db.base import Base


class CreditCostConfig(Base):
    """Global credit cost configuration per operation (independent of Plan)"""
    __tablename__ = "credit_cost_configs"

    id = Column(Integer, primary_key=True, index=True)
    operation = Column(String(50), nullable=False, unique=True, index=True)
    credit_cost = Column(Integer, nullable=False)
    description = Column(String(200), nullable=True)
    pricing_version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return (
            f"<CreditCostConfig(operation={self.operation!r}, "
            f"cost={self.credit_cost}, v={self.pricing_version})>"
        )
