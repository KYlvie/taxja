"""Transaction model with categories"""
import builtins
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from sqlalchemy import Column, Integer, String, Numeric, Date, Boolean, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.models.transaction_line_item import LineItemPostingType

# Save builtin property before SQLAlchemy relationship shadows it
_property = builtins.property


def _mirror_posting_type_for_transaction_type(
    transaction_type,
) -> LineItemPostingType:
    """Map a parent transaction type to a fallback posting type."""
    raw = getattr(transaction_type, "value", transaction_type)
    mapping = {
        TransactionType.INCOME.value: LineItemPostingType.INCOME,
        TransactionType.EXPENSE.value: LineItemPostingType.EXPENSE,
        TransactionType.ASSET_ACQUISITION.value: LineItemPostingType.ASSET_ACQUISITION,
        TransactionType.LIABILITY_DRAWDOWN.value: LineItemPostingType.LIABILITY_DRAWDOWN,
        TransactionType.LIABILITY_REPAYMENT.value: LineItemPostingType.LIABILITY_REPAYMENT,
        TransactionType.TAX_PAYMENT.value: LineItemPostingType.TAX_PAYMENT,
        TransactionType.TRANSFER.value: LineItemPostingType.TRANSFER,
    }
    return mapping.get(raw, LineItemPostingType.EXPENSE)


def _resolve_line_posting_type(transaction, line_item) -> LineItemPostingType:
    """Resolve posting type for real ORM rows and lightweight test doubles."""
    resolver = getattr(transaction, "_line_posting_type", None)
    if callable(resolver):
        return resolver(line_item)
    raw = getattr(line_item, "posting_type", None)
    if raw is None:
        return _mirror_posting_type_for_transaction_type(getattr(transaction, "type", None))
    if isinstance(raw, LineItemPostingType):
        return raw
    try:
        return LineItemPostingType(getattr(raw, "value", raw))
    except ValueError:
        return _mirror_posting_type_for_transaction_type(getattr(transaction, "type", None))


def _resolved_transaction_type(transaction) -> "TransactionType":
    """Return a transaction type with a safe legacy fallback."""
    raw = getattr(transaction, "type", None)
    if raw is None:
        return TransactionType.EXPENSE
    if isinstance(raw, TransactionType):
        return raw
    try:
        return TransactionType(getattr(raw, "value", raw))
    except ValueError:
        return TransactionType.EXPENSE


class TransactionType(str, Enum):
    """Transaction type enumeration"""
    INCOME = "income"
    EXPENSE = "expense"
    ASSET_ACQUISITION = "asset_acquisition"
    LIABILITY_DRAWDOWN = "liability_drawdown"
    LIABILITY_REPAYMENT = "liability_repayment"
    TAX_PAYMENT = "tax_payment"
    TRANSFER = "transfer"


class IncomeCategory(str, Enum):
    """Income category enumeration – mirrors Austrian 7 Einkunftsarten"""
    AGRICULTURE = "agriculture"  # Nr.1 Land- und Forstwirtschaft
    SELF_EMPLOYMENT = "self_employment"  # Nr.2 Selbständige Arbeit (Freiberufler)
    BUSINESS = "business"  # Nr.3 Gewerbebetrieb
    EMPLOYMENT = "employment"  # Nr.4 Nichtselbständige Arbeit
    CAPITAL_GAINS = "capital_gains"  # Nr.5 Kapitalvermögen
    RENTAL = "rental"  # Nr.6 Vermietung und Verpachtung
    OTHER_INCOME = "other_income"  # Nr.7 Sonstige Einkünfte


class VatType(str, Enum):
    """VAT transaction type for UVA/U1 reporting"""
    DOMESTIC = "domestic"                    # Standard domestic transaction
    INTRA_COMMUNITY = "intra_community"      # IG-Erwerb / innergemeinschaftlich
    REVERSE_CHARGE = "reverse_charge"        # §19 Abs.1 UStG
    IMPORT = "import"                        # Einfuhrumsatzsteuer
    EXEMPT = "exempt"                        # Steuerbefreit


class ExpenseCategory(str, Enum):
    """Expense category enumeration"""
    OFFICE_SUPPLIES = "office_supplies"
    EQUIPMENT = "equipment"
    TRAVEL = "travel"
    MARKETING = "marketing"
    PROFESSIONAL_SERVICES = "professional_services"
    INSURANCE = "insurance"
    MAINTENANCE = "maintenance"
    PROPERTY_TAX = "property_tax"
    LOAN_INTEREST = "loan_interest"
    DEPRECIATION = "depreciation"
    GROCERIES = "groceries"          # Wareneinsatz / materials
    UTILITIES = "utilities"
    COMMUTING = "commuting"
    HOME_OFFICE = "home_office"
    VEHICLE = "vehicle"              # KFZ-Aufwand
    TELECOM = "telecom"              # Nachrichtenaufwand (phone, internet, postage)
    RENT = "rent"                    # Mietaufwand (business premises rent)
    BANK_FEES = "bank_fees"          # Spesen des Geldverkehrs
    SVS_CONTRIBUTIONS = "svs_contributions"  # SVA/SVS Pflichtbeiträge
    # Industry-specific expense categories
    CLEANING = "cleaning"                # Reinigungsmittel / cleaning supplies
    CLOTHING = "clothing"                # Arbeitskleidung / work clothing
    SOFTWARE = "software"                # Software-Lizenzen / licenses
    SHIPPING = "shipping"                # Versandkosten / shipping
    FUEL = "fuel"                        # Treibstoff / fuel
    EDUCATION = "education"              # Fortbildung / professional development
    # Property-related expense categories
    PROPERTY_MANAGEMENT_FEES = "property_management_fees"  # Hausverwaltung
    PROPERTY_INSURANCE = "property_insurance"  # Gebäudeversicherung
    DEPRECIATION_AFA = "depreciation_afa"  # Absetzung für Abnutzung
    OTHER = "other"


def _transaction_type_db_labels(enum_cls):
    return [member.name for member in enum_cls]


def _income_category_db_labels(enum_cls):
    return [member.name for member in enum_cls]


def _expense_category_db_labels(enum_cls):
    legacy_lowercase_members = {
        ExpenseCategory.CLEANING,
        ExpenseCategory.CLOTHING,
        ExpenseCategory.SOFTWARE,
        ExpenseCategory.SHIPPING,
        ExpenseCategory.FUEL,
        ExpenseCategory.EDUCATION,
    }
    return [
        member.value if member in legacy_lowercase_members else member.name
        for member in enum_cls
    ]


TRANSACTION_TYPE_ENUM = SQLEnum(
    TransactionType,
    name="transactiontype",
    values_callable=_transaction_type_db_labels,
    validate_strings=True,
)

INCOME_CATEGORY_ENUM = SQLEnum(
    IncomeCategory,
    name="incomecategory",
    values_callable=_income_category_db_labels,
    validate_strings=True,
)

EXPENSE_CATEGORY_ENUM = SQLEnum(
    ExpenseCategory,
    name="expensecategory",
    values_callable=_expense_category_db_labels,
    validate_strings=True,
)


class Transaction(Base):
    """Transaction model for income and expenses"""
    __tablename__ = "transactions"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Foreign key to property (nullable - not all transactions are property-related)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="SET NULL"), nullable=True, index=True)
    liability_id = Column(Integer, ForeignKey("liabilities.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Transaction type
    type = Column(TRANSACTION_TYPE_ENUM, nullable=False, index=True)
    
    # Amount (always positive, type determines income/expense)
    amount = Column(Numeric(12, 2), nullable=False)
    
    # Transaction date
    transaction_date = Column(Date, nullable=False, index=True)
    
    # Description
    description = Column(String(500))
    
    # Categories (only one should be set based on type)
    income_category = Column(INCOME_CATEGORY_ENUM, nullable=True)
    expense_category = Column(EXPENSE_CATEGORY_ENUM, nullable=True)
    
    # Deductibility
    is_deductible = Column(Boolean, default=False)
    deduction_reason = Column(String(500))
    
    # VAT information
    vat_rate = Column(Numeric(5, 4), nullable=True)  # e.g., 0.20 for 20%
    vat_amount = Column(Numeric(12, 2), nullable=True)
    vat_type = Column(String(50), nullable=True, default="DOMESTIC")
    
    # Foreign key to document (for OCR integration)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    
    # Classification confidence (0.0 to 1.0)
    classification_confidence = Column(Numeric(3, 2), nullable=True)

    # Classification method: rule, ml, llm, manual, or None
    classification_method = Column(String(20), nullable=True)

    # Review flag
    needs_review = Column(Boolean, default=False)
    
    # Historical import review and lock flags
    reviewed = Column(Boolean, default=False, nullable=False)  # Manually reviewed by user
    locked = Column(Boolean, default=False, nullable=False)  # Locked from auto-modifications
    
    # System-generated flag (for depreciation transactions)
    is_system_generated = Column(Boolean, default=False, nullable=False)
    
    # AI review gate notes (reason for flagging)
    ai_review_notes = Column(String(500), nullable=True)

    # Import source
    import_source = Column(String(50), nullable=True)  # csv, psd2, manual, ocr
    
    # Recurring transaction fields
    is_recurring = Column(Boolean, default=False, nullable=False)
    recurring_frequency = Column(String(20), nullable=True)  # monthly, quarterly, yearly, weekly
    recurring_start_date = Column(Date, nullable=True)
    recurring_end_date = Column(Date, nullable=True)
    recurring_day_of_month = Column(Integer, nullable=True)
    recurring_is_active = Column(Boolean, default=True, nullable=False)
    recurring_next_date = Column(Date, nullable=True)
    recurring_last_generated = Column(Date, nullable=True)
    parent_recurring_id = Column(Integer, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True, index=True)
    source_recurring_id = Column(Integer, ForeignKey("recurring_transactions.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    property = relationship("Property", back_populates="transactions", foreign_keys=[property_id])
    liability = relationship("Liability", back_populates="transactions", foreign_keys=[liability_id])
    corrections = relationship("ClassificationCorrection", back_populates="transaction")
    line_items = relationship(
        "TransactionLineItem", back_populates="transaction",
        cascade="all, delete-orphan", order_by="TransactionLineItem.sort_order",
    )
    source_recurring = relationship("RecurringTransaction", foreign_keys=[source_recurring_id])
    generated_transactions = relationship("Transaction", backref="parent_recurring", remote_side=[id], foreign_keys=[parent_recurring_id])
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, type={self.type}, amount={self.amount}, date={self.transaction_date})>"

    # --- Line-item aware helpers ---

    @_property
    def has_line_items(self) -> bool:
        """Whether this transaction has per-item breakdown."""
        raw_line_items = getattr(self, "line_items", None)
        if raw_line_items is None:
            return False
        try:
            return len(raw_line_items) > 0
        except Exception:
            try:
                return bool(list(raw_line_items))
            except Exception:
                return False

    def _default_line_posting_type(self) -> LineItemPostingType:
        """Map the parent cash-event type to a mirror posting type."""
        return _mirror_posting_type_for_transaction_type(_resolved_transaction_type(self))

    def _line_posting_type(self, line_item) -> LineItemPostingType:
        """Resolve a line item's posting type with safe fallback for legacy rows."""
        raw = getattr(line_item, "posting_type", None)
        if raw is None:
            return self._default_line_posting_type()
        if isinstance(raw, LineItemPostingType):
            return raw
        try:
            return LineItemPostingType(getattr(raw, "value", raw))
        except ValueError:
            return self._default_line_posting_type()

    @_property
    def posting_gross_amount(self) -> Decimal:
        """Gross amount reconstructed from canonical posting lines."""
        if not self.line_items:
            return self.amount or Decimal("0.00")
        total = Decimal("0.00")
        for li in self.line_items:
            qty = getattr(li, "quantity", 1) or 1
            line_amount = getattr(li, "amount", Decimal("0.00")) or Decimal("0.00")
            recoverable_vat = getattr(li, "vat_recoverable_amount", Decimal("0.00")) or Decimal("0.00")
            total += (line_amount * qty) + recoverable_vat
        return total

    @_property
    def bookkeeping_expense_amount(self) -> Decimal:
        """Total expense postings that belong in bookkeeping/GuV."""
        if not self.line_items:
            return (
                self.amount or Decimal("0.00")
            ) if _resolved_transaction_type(self) == TransactionType.EXPENSE else Decimal("0.00")
        return sum(
            (
                (li.amount or Decimal("0.00")) * (li.quantity or 1)
                for li in self.line_items
                if _resolve_line_posting_type(self, li) == LineItemPostingType.EXPENSE
            ),
            Decimal("0.00"),
        )

    @_property
    def private_use_amount(self) -> Decimal:
        """Private-use postings excluded from business expense totals."""
        if not self.line_items:
            return Decimal("0.00")
        return sum(
            (
                (li.amount or Decimal("0.00")) * (li.quantity or 1)
                for li in self.line_items
                if _resolve_line_posting_type(self, li) == LineItemPostingType.PRIVATE_USE
            ),
            Decimal("0.00"),
        )

    @_property
    def vat_recoverable_amount_total(self) -> Decimal:
        """Recoverable VAT captured on canonical line items."""
        if not self.line_items:
            return Decimal("0.00")
        return sum(
            (
                getattr(li, "vat_recoverable_amount", Decimal("0.00")) or Decimal("0.00")
                for li in self.line_items
            ),
            Decimal("0.00"),
        )

    @_property
    def deductible_amount(self) -> Decimal:
        """Total deductible amount: sum of deductible line items, or full amount if no items."""
        if not self.line_items:
            return (
                self.amount or Decimal("0.00")
                if _resolved_transaction_type(self) == TransactionType.EXPENSE and self.is_deductible
                else Decimal("0.00")
            )
        return sum(
            (
                (li.amount or Decimal("0.00")) * (li.quantity or 1)
                for li in self.line_items
                if (
                    _resolve_line_posting_type(self, li) == LineItemPostingType.EXPENSE
                    and getattr(li, "is_deductible", False)
                )
            ),
            Decimal("0.00"),
        )

    @_property
    def non_deductible_amount(self) -> Decimal:
        """Total non-deductible amount."""
        if not self.line_items:
            if _resolved_transaction_type(self) != TransactionType.EXPENSE:
                return Decimal("0.00")
            return Decimal("0.00") if self.is_deductible else (self.amount or Decimal("0.00"))
        return sum(
            (
                (li.amount or Decimal("0.00")) * (li.quantity or 1)
                for li in self.line_items
                if (
                    _resolve_line_posting_type(self, li) == LineItemPostingType.PRIVATE_USE
                    or (
                        _resolve_line_posting_type(self, li) == LineItemPostingType.EXPENSE
                        and not getattr(li, "is_deductible", False)
                    )
                )
            ),
            Decimal("0.00"),
        )

    @_property
    def deductible_items_by_category(self) -> dict:
        """Group deductible line items by category → total amount.

        Returns e.g. {"office_supplies": Decimal("12.50"), "cleaning": Decimal("5.30")}
        Used by tax reports to aggregate expenses per category accurately.
        """
        if not self.line_items:
            if _resolved_transaction_type(self) == TransactionType.EXPENSE and self.is_deductible:
                cat = (
                    self.expense_category.value
                    if self.expense_category
                    else "other"
                )
                return {cat: self.amount or Decimal("0.00")}
            return {}
        result: dict = {}
        for li in self.line_items:
            if (
                _resolve_line_posting_type(self, li) == LineItemPostingType.EXPENSE
                and getattr(li, "is_deductible", False)
                and li.category
            ):
                result[li.category] = result.get(li.category, Decimal("0.00")) + (
                    (li.amount or Decimal("0.00")) * (li.quantity or 1)
                )
        return result
