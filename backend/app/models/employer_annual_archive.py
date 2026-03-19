"""Historical annual payroll archive models for employer-light support."""
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class EmployerAnnualArchiveStatus(str, Enum):
    """State machine for archived historical annual payroll packs."""

    PENDING_CONFIRMATION = "pending_confirmation"
    ARCHIVED = "archived"


class EmployerAnnualArchive(Base):
    """One archived payroll pack per historical tax year."""

    __tablename__ = "employer_annual_archives"
    __table_args__ = (
        UniqueConstraint("user_id", "tax_year", name="uq_employer_annual_archive_user_year"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tax_year = Column(Integer, nullable=False, index=True)
    status = Column(
        SQLEnum(EmployerAnnualArchiveStatus),
        nullable=False,
        default=EmployerAnnualArchiveStatus.PENDING_CONFIRMATION,
        index=True,
    )

    source_type = Column(String(30), nullable=True)
    archive_signal = Column(String(50), nullable=True)
    confidence = Column(Numeric(3, 2), nullable=True)

    employer_name = Column(String(255), nullable=True)
    gross_income = Column(Numeric(12, 2), nullable=True)
    withheld_tax = Column(Numeric(12, 2), nullable=True)
    notes = Column(Text, nullable=True)

    confirmed_at = Column(DateTime, nullable=True)
    last_signal_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="employer_annual_archives")
    document_links = relationship(
        "EmployerAnnualArchiveDocument",
        back_populates="annual_archive",
        cascade="all, delete-orphan",
    )


class EmployerAnnualArchiveDocument(Base):
    """Links supporting annual payroll documents to an archived tax year."""

    __tablename__ = "employer_annual_archive_documents"
    __table_args__ = (
        UniqueConstraint(
            "annual_archive_id",
            "document_id",
            name="uq_employer_annual_archive_document",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    annual_archive_id = Column(
        Integer,
        ForeignKey("employer_annual_archives.id"),
        nullable=False,
        index=True,
    )
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    relation_type = Column(String(30), nullable=False, default="supporting")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    annual_archive = relationship("EmployerAnnualArchive", back_populates="document_links")
    document = relationship("Document")
