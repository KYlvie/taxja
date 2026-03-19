"""Classification correction model for storing user corrections"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class ClassificationCorrection(Base):
    """
    Store user corrections to transaction classifications.
    
    This data is used to retrain the ML model and improve classification accuracy.
    """
    __tablename__ = "classification_corrections"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Original classification
    original_category = Column(String, nullable=False)
    original_confidence = Column(String, nullable=True)
    
    # Corrected classification
    correct_category = Column(String, nullable=False)

    # Source of the correction — used to filter training data.
    # Values: "human_verified", "llm_verified", "llm_unverified", "system_default"
    # ML retraining should only use "human_verified" and "llm_verified".
    source = Column(String(30), nullable=True, default="human_verified")

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    transaction = relationship("Transaction", back_populates="corrections")
    user = relationship("User", back_populates="corrections")
    
    def __repr__(self):
        return f"<ClassificationCorrection(id={self.id}, transaction_id={self.transaction_id}, {self.original_category} -> {self.correct_category})>"
