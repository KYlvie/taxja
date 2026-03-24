"""Bank statement import models for the bank workbench flow."""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class BankStatementImportSourceType(str, Enum):
    """Source channel for a bank statement import."""

    CSV = "csv"
    MT940 = "mt940"
    DOCUMENT = "document"


class BankStatementLineStatus(str, Enum):
    """Review status for a bank statement line."""

    PENDING_REVIEW = "pending_review"
    AUTO_CREATED = "auto_created"
    MATCHED_EXISTING = "matched_existing"
    IGNORED_DUPLICATE = "ignored_duplicate"


class BankStatementSuggestedAction(str, Enum):
    """Suggested next action for a bank statement line."""

    CREATE_NEW = "create_new"
    MATCH_EXISTING = "match_existing"
    IGNORE = "ignore"


class BankStatementImport(Base):
    """Represents one imported bank statement or bank-statement document."""

    __tablename__ = "bank_statement_imports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(
        SQLEnum(
            BankStatementImportSourceType,
            name="bankstatementimportsourcetype",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )
    source_document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    bank_name = Column(String(255), nullable=True)
    iban = Column(String(64), nullable=True)
    statement_period = Column(JSON, nullable=True)
    tax_year = Column(Integer, nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="bank_statement_imports")
    source_document = relationship("Document", back_populates="bank_statement_imports")
    lines = relationship(
        "BankStatementLine",
        back_populates="statement_import",
        cascade="all, delete-orphan",
        order_by="BankStatementLine.line_date, BankStatementLine.id",
    )


class BankStatementLine(Base):
    """One statement line imported into the bank workbench."""

    __tablename__ = "bank_statement_lines"

    id = Column(Integer, primary_key=True, index=True)
    import_id = Column(
        Integer,
        ForeignKey("bank_statement_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    line_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    counterparty = Column(String(255), nullable=True)
    purpose = Column(String(1000), nullable=True)
    raw_reference = Column(String(255), nullable=True)
    normalized_fingerprint = Column(String(255), nullable=False, index=True)
    review_status = Column(
        SQLEnum(
            BankStatementLineStatus,
            name="bankstatementlinestatus",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=BankStatementLineStatus.PENDING_REVIEW,
        index=True,
    )
    suggested_action = Column(
        SQLEnum(
            BankStatementSuggestedAction,
            name="bankstatementsuggestedaction",
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=BankStatementSuggestedAction.CREATE_NEW,
    )
    confidence_score = Column(Numeric(4, 3), nullable=False, default=0)
    linked_transaction_id = Column(
        Integer,
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_transaction_id = Column(
        Integer,
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    statement_import = relationship("BankStatementImport", back_populates="lines")
    linked_transaction = relationship(
        "Transaction",
        foreign_keys=[linked_transaction_id],
    )
    created_transaction = relationship(
        "Transaction",
        foreign_keys=[created_transaction_id],
    )
    reviewer = relationship("User", foreign_keys=[reviewed_by])
