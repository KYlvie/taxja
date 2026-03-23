"""TaxFilingData model for storing extracted and confirmed tax document data"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class TaxFilingData(Base):
    """Stores structured data extracted from tax documents (L16, L1, E1a, E1b, etc.)

    Acts as an intermediate layer between raw OCR extraction and final tax reports.
    Users confirm extracted data, which is then available for tax calculations.
    """

    __tablename__ = "tax_filing_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tax_year = Column(Integer, nullable=False, index=True)
    data_type = Column(String(50), nullable=False, index=True)  # l16, l1, e1a, e1b, etc.
    source_document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    data = Column(JSON, nullable=False)  # Extracted structured data
    status = Column(String(20), default="pending")  # pending / confirmed / rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User")
    source_document = relationship("Document")

    def __repr__(self):
        return (
            f"<TaxFilingData(id={self.id}, type={self.data_type}, "
            f"year={self.tax_year}, status={self.status})>"
        )
