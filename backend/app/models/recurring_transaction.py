"""RecurringTransaction model for automated transaction generation"""
from datetime import datetime, date
from enum import Enum
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Enum as SQLEnum, Boolean, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.models.transaction import TransactionType


class RecurrenceFrequency(str, Enum):
    """Recurrence frequency enumeration"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUALLY = "annually"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"


class RecurringTransactionType(str, Enum):
    """Type of recurring transaction"""
    RENTAL_INCOME = "rental_income"  # Rental income from property
    LOAN_INTEREST = "loan_interest"  # Loan interest payment
    DEPRECIATION = "depreciation"  # Annual depreciation
    OTHER_INCOME = "other_income"  # Other recurring income
    OTHER_EXPENSE = "other_expense"  # Other recurring expense
    MANUAL = "manual"  # User-defined recurring transaction
    INSURANCE_PREMIUM = "insurance_premium"  # Insurance premium payment
    LOAN_REPAYMENT = "loan_repayment"  # Standalone loan repayment


VALID_TRANSACTION_TYPE_VALUES = tuple(transaction_type.value for transaction_type in TransactionType)
VALID_TRANSACTION_TYPE_CHECK_SQL = (
    "transaction_type IN ("
    + ", ".join(f"'{value}'" for value in VALID_TRANSACTION_TYPE_VALUES)
    + ")"
)


class RecurringTransaction(Base):
    """RecurringTransaction model for automated transaction generation"""
    __tablename__ = "recurring_transactions"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Type and source
    recurring_type = Column(SQLEnum(RecurringTransactionType, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    
    # Optional foreign keys to source entities
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=True, index=True)
    loan_id = Column(Integer, ForeignKey("property_loans.id", ondelete="CASCADE"), nullable=True, index=True)
    liability_id = Column(Integer, ForeignKey("liabilities.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Transaction details
    description = Column(String(500), nullable=False)
    amount = Column(
        Numeric(12, 2), 
        nullable=False,
        info={"check": "amount > 0"}
    )
    transaction_type = Column(String(20), nullable=False)
    category = Column(String(100), nullable=False)
    
    # Recurrence settings
    frequency = Column(SQLEnum(RecurrenceFrequency, values_callable=lambda x: [e.value for e in x]), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # Null = indefinite
    
    # Day of month for monthly/quarterly/annual (1-31)
    day_of_month = Column(Integer, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    paused_at = Column(DateTime, nullable=True)
    
    # Last generation tracking
    last_generated_date = Column(Date, nullable=True)
    next_generation_date = Column(Date, nullable=True, index=True)
    
    # Template for common recurring transactions
    template = Column(String(50), nullable=True)  # e.g., "svs", "wko", "office_rent", "software_subscription"
    
    # Source document that created this recurring transaction (OCR pipeline)
    source_document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)

    # Rental unit percentage (what share of the property this rental unit represents)
    # e.g. Thenneberg 51/3 = 33% of Thenneberg 51
    unit_percentage = Column(Numeric(5, 2), nullable=True)

    # Metadata
    notes = Column(String(1000), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="check_amount_positive"
        ),
        CheckConstraint(
            VALID_TRANSACTION_TYPE_CHECK_SQL,
            name="check_transaction_type_valid"
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="check_end_date_after_start"
        ),
        CheckConstraint(
            "day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31)",
            name="check_day_of_month_range"
        ),
        CheckConstraint(
            "(recurring_type = 'rental_income' AND property_id IS NOT NULL) OR "
            "(recurring_type = 'loan_interest' AND (loan_id IS NOT NULL OR liability_id IS NOT NULL)) OR "
            "(recurring_type = 'depreciation' AND property_id IS NOT NULL) OR "
            # Keep legacy loan repayment schedules valid even when they predate
            # liability_id / loan_id linkage. API-layer validation still enforces
            # liability binding for newly created non-property liabilities.
            "(recurring_type = 'loan_repayment') OR "
            "(recurring_type IN ('other_income', 'other_expense', 'manual', 'insurance_premium'))",
            name="check_source_entity_required"
        ),
    )
    
    # Relationships
    user = relationship("User", back_populates="recurring_transactions")
    property = relationship("Property", foreign_keys=[property_id])
    loan = relationship("PropertyLoan", foreign_keys=[loan_id])
    liability = relationship("Liability", back_populates="recurring_transactions", foreign_keys=[liability_id])
    
    def __repr__(self):
        return f"<RecurringTransaction(id={self.id}, type={self.recurring_type}, amount={self.amount}, frequency={self.frequency})>"
    
    def should_generate_for_date(self, target_date: date) -> bool:
        """
        Check if a transaction should be generated for the given date.
        
        Args:
            target_date: Date to check
            
        Returns:
            True if transaction should be generated
        """
        if not self.is_active:
            return False
        
        if target_date < self.start_date:
            return False
        
        if self.end_date and target_date > self.end_date:
            return False
        
        if self.last_generated_date and target_date <= self.last_generated_date:
            return False
        
        return True
    
    def calculate_next_date(self, from_date: date) -> date:
        """
        Calculate the next generation date based on frequency.
        
        Args:
            from_date: Date to calculate from
            
        Returns:
            Next generation date
        """
        import calendar

        if self.frequency == RecurrenceFrequency.WEEKLY:
            from datetime import timedelta
            return from_date + timedelta(weeks=1)
        elif self.frequency == RecurrenceFrequency.BIWEEKLY:
            from datetime import timedelta
            return from_date + timedelta(weeks=2)
        elif self.frequency == RecurrenceFrequency.MONTHLY:
            # Simple month addition
            year = from_date.year
            month = from_date.month + 1
            if month > 12:
                month = 1
                year += 1
            target_day = self.day_of_month or from_date.day
            max_day = calendar.monthrange(year, month)[1]
            day = min(target_day, max_day)
            return date(year, month, day)
        elif self.frequency == RecurrenceFrequency.QUARTERLY:
            # Add 3 months
            year = from_date.year
            month = from_date.month + 3
            while month > 12:
                month -= 12
                year += 1
            target_day = self.day_of_month or from_date.day
            max_day = calendar.monthrange(year, month)[1]
            day = min(target_day, max_day)
            return date(year, month, day)
        elif self.frequency == RecurrenceFrequency.SEMI_ANNUAL:
            # Add 6 months
            year = from_date.year
            month = from_date.month + 6
            while month > 12:
                month -= 12
                year += 1
            target_day = self.day_of_month or from_date.day
            max_day = calendar.monthrange(year, month)[1]
            day = min(target_day, max_day)
            return date(year, month, day)
        elif self.frequency == RecurrenceFrequency.ANNUALLY:
            # Add 1 year
            year = from_date.year + 1
            month = from_date.month
            target_day = self.day_of_month or from_date.day
            max_day = calendar.monthrange(year, month)[1]
            day = min(target_day, max_day)
            return date(year, month, day)
        
        return from_date
