"""PropertyLoan model for tracking property financing"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class PropertyLoan(Base):
    """PropertyLoan model for tracking property financing and loan interest"""
    __tablename__ = "property_loans"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to property
    property_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("properties.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Foreign key to user (for easier querying)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Loan details
    loan_amount = Column(
        Numeric(12, 2), 
        nullable=False,
        info={"check": "loan_amount > 0"}
    )
    
    interest_rate = Column(
        Numeric(5, 4), 
        nullable=False,
        info={"check": "interest_rate >= 0 AND interest_rate <= 0.20"}  # 0% to 20%
    )
    
    # Loan period
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # Nullable for open-ended loans
    
    # Payment information
    monthly_payment = Column(
        Numeric(12, 2), 
        nullable=False,
        info={"check": "monthly_payment > 0"}
    )
    
    # Lender information
    lender_name = Column(String(255), nullable=False)
    lender_account = Column(String(100), nullable=True)  # IBAN or account number
    
    # Loan type (optional)
    loan_type = Column(String(50), nullable=True)  # e.g., "fixed_rate", "variable_rate", "annuity"
    
    # Document reference
    loan_contract_document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    
    # Notes
    notes = Column(String(1000), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "loan_amount > 0",
            name="check_loan_amount_positive"
        ),
        CheckConstraint(
            "interest_rate >= 0 AND interest_rate <= 0.20",
            name="check_interest_rate_range"
        ),
        CheckConstraint(
            "monthly_payment > 0",
            name="check_monthly_payment_positive"
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="check_end_date_after_start"
        ),
    )
    
    # Relationships
    property = relationship("Property", back_populates="loans")
    user = relationship("User", back_populates="property_loans")
    
    def __repr__(self):
        return f"<PropertyLoan(id={self.id}, property_id={self.property_id}, lender={self.lender_name}, amount={self.loan_amount})>"
    
    def calculate_remaining_balance(self, as_of_date: datetime.date) -> Decimal:
        """
        Calculate remaining loan balance as of a specific date.
        
        This is a simplified calculation. For accurate amortization schedules,
        use the LoanService which handles principal/interest splits.
        
        Args:
            as_of_date: Date to calculate balance for
            
        Returns:
            Estimated remaining balance
        """
        if as_of_date < self.start_date:
            return Decimal("0")
        
        if self.end_date and as_of_date >= self.end_date:
            return Decimal("0")
        
        # Simple calculation: original amount minus payments made
        # This is approximate - actual calculation should account for interest
        months_elapsed = (as_of_date.year - self.start_date.year) * 12 + (as_of_date.month - self.start_date.month)
        
        if months_elapsed <= 0:
            return self.loan_amount
        
        # This is a placeholder - real calculation needs amortization schedule
        # For now, return original amount (will be improved in LoanService)
        return self.loan_amount
    
    def calculate_annual_interest(self, year: int) -> Decimal:
        """
        Calculate total interest paid in a specific year.
        
        This is a simplified calculation. For accurate interest calculations,
        use the LoanService which handles amortization schedules.
        
        Args:
            year: Tax year to calculate interest for
            
        Returns:
            Estimated annual interest paid
        """
        # Simple calculation: average balance * interest rate
        # This is approximate - actual calculation should use amortization schedule
        annual_interest = self.loan_amount * self.interest_rate
        
        # Pro-rate for partial years
        if year == self.start_date.year:
            months_in_year = 12 - self.start_date.month + 1
            annual_interest = annual_interest * Decimal(months_in_year) / Decimal(12)
        
        if self.end_date and year == self.end_date.year:
            months_in_year = self.end_date.month
            annual_interest = annual_interest * Decimal(months_in_year) / Decimal(12)
        
        return annual_interest.quantize(Decimal("0.01"))
