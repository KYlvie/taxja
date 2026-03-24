"""Employer-light monthly compliance models."""
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


class EmployerMonthStatus(str, Enum):
    """Lightweight state machine for employer-month handling."""

    UNKNOWN = "unknown"
    PAYROLL_DETECTED = "payroll_detected"
    MISSING_CONFIRMATION = "missing_confirmation"
    NO_PAYROLL_CONFIRMED = "no_payroll_confirmed"
    ARCHIVED_YEAR_ONLY = "archived_year_only"


class EmployerMonth(Base):
    """Monthly employer facts and confirmations for non-HR payroll support."""

    __tablename__ = "employer_months"
    __table_args__ = (
        UniqueConstraint("user_id", "year_month", name="uq_employer_month_user_month"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    year_month = Column(String(7), nullable=False, index=True)  # YYYY-MM
    status = Column(
        SQLEnum(EmployerMonthStatus),
        nullable=False,
        default=EmployerMonthStatus.UNKNOWN,
        index=True,
    )

    source_type = Column(String(30), nullable=True)  # document, ai_confirm, manual_summary
    payroll_signal = Column(String(50), nullable=True)  # payslip, lohnzettel, payroll_bundle, etc.
    confidence = Column(Numeric(3, 2), nullable=True)

    employee_count = Column(Integer, nullable=True)
    gross_wages = Column(Numeric(12, 2), nullable=True)
    net_paid = Column(Numeric(12, 2), nullable=True)
    employer_social_cost = Column(Numeric(12, 2), nullable=True)
    lohnsteuer = Column(Numeric(12, 2), nullable=True)
    db_amount = Column(Numeric(12, 2), nullable=True)
    dz_amount = Column(Numeric(12, 2), nullable=True)
    kommunalsteuer = Column(Numeric(12, 2), nullable=True)
    special_payments = Column(Numeric(12, 2), nullable=True)

    notes = Column(Text, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    last_signal_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="employer_months")
    document_links = relationship(
        "EmployerMonthDocument",
        back_populates="employer_month",
        cascade="all, delete-orphan",
    )


class EmployerMonthDocument(Base):
    """Links supporting documents to an employer month."""

    __tablename__ = "employer_month_documents"
    __table_args__ = (
        UniqueConstraint("employer_month_id", "document_id", name="uq_employer_month_document"),
    )

    id = Column(Integer, primary_key=True, index=True)
    employer_month_id = Column(Integer, ForeignKey("employer_months.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(String(30), nullable=False, default="supporting")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    employer_month = relationship("EmployerMonth", back_populates="document_links")
    document = relationship("Document")
