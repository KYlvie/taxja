"""Unified liability master data model."""
from datetime import datetime, date
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


def _enum_values(enum_cls):
    return [member.value for member in enum_cls]


class LiabilityType(str, Enum):
    PROPERTY_LOAN = "property_loan"
    BUSINESS_LOAN = "business_loan"
    OWNER_LOAN = "owner_loan"
    FAMILY_LOAN = "family_loan"
    OTHER_LIABILITY = "other_liability"


class LiabilitySourceType(str, Enum):
    MANUAL = "manual"
    DOCUMENT_CONFIRMED = "document_confirmed"
    DOCUMENT_AUTO_CREATED = "document_auto_created"
    SYSTEM_MIGRATED = "system_migrated"


class LiabilityReportCategory(str, Enum):
    DARLEHEN_UND_KREDITE = "darlehen_und_kredite"
    SONSTIGE_VERBINDLICHKEITEN = "sonstige_verbindlichkeiten"


class Liability(Base):
    """Unified liability table for debt management and reporting."""

    __tablename__ = "liabilities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    liability_type = Column(
        SQLEnum(LiabilityType, name="liabilitytype", values_callable=_enum_values),
        nullable=False,
        index=True,
    )
    source_type = Column(
        SQLEnum(LiabilitySourceType, name="liabilitysourcetype", values_callable=_enum_values),
        nullable=False,
        default=LiabilitySourceType.MANUAL,
        index=True,
    )
    display_name = Column(String(255), nullable=False)
    currency = Column(String(3), nullable=False, default="EUR")
    lender_name = Column(String(255), nullable=False)
    principal_amount = Column(Numeric(12, 2), nullable=False)
    outstanding_balance = Column(Numeric(12, 2), nullable=False)
    interest_rate = Column(Numeric(8, 6), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    monthly_payment = Column(Numeric(12, 2), nullable=True)
    tax_relevant = Column(Boolean, nullable=False, default=False, index=True)
    tax_relevance_reason = Column(String(500), nullable=True)
    report_category = Column(
        SQLEnum(
            LiabilityReportCategory,
            name="liabilityreportcategory",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    linked_property_id = Column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    linked_loan_id = Column(
        Integer,
        ForeignKey("property_loans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    notes = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="liabilities")
    linked_property = relationship("Property", back_populates="liabilities", foreign_keys=[linked_property_id])
    linked_loan = relationship("PropertyLoan", back_populates="liability", foreign_keys=[linked_loan_id])
    source_document = relationship("Document", foreign_keys=[source_document_id])
    transactions = relationship("Transaction", back_populates="liability")
    recurring_transactions = relationship("RecurringTransaction", back_populates="liability")

    @property
    def is_open_ended(self) -> bool:
        return self.end_date is None

    def derive_active_state(self, today: date | None = None) -> bool:
        today = today or date.today()
        return self.end_date is None or self.end_date >= today

    @property
    def is_document_backed(self) -> bool:
        return bool(self.source_document_id) or self.source_type in {
            LiabilitySourceType.DOCUMENT_CONFIRMED,
            LiabilitySourceType.DOCUMENT_AUTO_CREATED,
        }

    @property
    def can_edit_directly(self) -> bool:
        return (
            self.source_type == LiabilitySourceType.MANUAL
            and self.source_document_id is None
            and self.linked_loan_id is None
        )

    @property
    def can_deactivate_directly(self) -> bool:
        return self.can_edit_directly

    @property
    def edit_via_document(self) -> bool:
        return self.source_document_id is not None

    @property
    def requires_supporting_document(self) -> bool:
        return self.source_type == LiabilitySourceType.MANUAL and self.source_document_id is None

    @property
    def recommended_document_type(self) -> str:
        return "loan_contract" if self.liability_type != LiabilityType.OTHER_LIABILITY else "other"

    def __repr__(self) -> str:
        return (
            f"<Liability(id={self.id}, type={self.liability_type}, source={self.source_type}, "
            f"balance={self.outstanding_balance}, lender={self.lender_name})>"
        )
