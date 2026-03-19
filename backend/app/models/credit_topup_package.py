"""CreditTopupPackage model for predefined credit top-up packages"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from app.db.base import Base


class CreditTopupPackage(Base):
    """Predefined credit top-up packages available for purchase"""
    __tablename__ = "credit_topup_packages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    credits = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    stripe_price_id = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<CreditTopupPackage(id={self.id}, name={self.name}, "
            f"credits={self.credits}, price={self.price})>"
        )
