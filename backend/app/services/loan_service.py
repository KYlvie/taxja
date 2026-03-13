"""LoanService for property loan management and amortization calculations"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import extract, and_

from app.models.property_loan import PropertyLoan
from app.models.property import Property
from app.models.transaction import Transaction, TransactionType, ExpenseCategory


class AmortizationScheduleEntry:
    """Single entry in an amortization schedule"""
    def __init__(
        self,
        payment_number: int,
        payment_date: date,
        payment_amount: Decimal,
        principal_amount: Decimal,
        interest_amount: Decimal,
        remaining_balance: Decimal
    ):
        self.payment_number = payment_number
        self.payment_date = payment_date
        self.payment_amount = payment_amount
        self.principal_amount = principal_amount
        self.interest_amount = interest_amount
        self.remaining_balance = remaining_balance
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "payment_number": self.payment_number,
            "payment_date": self.payment_date.isoformat(),
            "payment_amount": float(self.payment_amount),
            "principal_amount": float(self.principal_amount),
            "interest_amount": float(self.interest_amount),
            "remaining_balance": float(self.remaining_balance)
        }


class LoanService:
    """Service for managing property loans and calculating amortization schedules"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_loan(
        self,
        user_id: int,
        property_id: UUID,
        loan_amount: Decimal,
        interest_rate: Decimal,
        start_date: date,
        monthly_payment: Decimal,
        lender_name: str,
        end_date: Optional[date] = None,
        lender_account: Optional[str] = None,
        loan_type: Optional[str] = None,
        notes: Optional[str] = None
    ) -> PropertyLoan:
        """
        Create a new property loan.
        
        Args:
            user_id: User ID (ownership validation)
            property_id: Property ID to link loan to
            loan_amount: Principal loan amount
            interest_rate: Annual interest rate (as decimal, e.g., 0.0325 for 3.25%)
            start_date: Loan start date
            monthly_payment: Monthly payment amount
            lender_name: Name of lending institution
            end_date: Loan end date (optional for open-ended loans)
            lender_account: IBAN or account number (optional)
            loan_type: Type of loan (optional)
            notes: Additional notes (optional)
            
        Returns:
            Created PropertyLoan instance
            
        Raises:
            ValueError: If property doesn't exist or doesn't belong to user
        """
        # Validate property ownership
        property = self.db.query(Property).filter(
            Property.id == property_id,
            Property.user_id == user_id
        ).first()
        
        if not property:
            raise ValueError("Property not found or does not belong to user")
        
        # Create loan
        loan = PropertyLoan(
            user_id=user_id,
            property_id=property_id,
            loan_amount=loan_amount,
            interest_rate=interest_rate,
            start_date=start_date,
            end_date=end_date,
            monthly_payment=monthly_payment,
            lender_name=lender_name,
            lender_account=lender_account,
            loan_type=loan_type,
            notes=notes
        )
        
        self.db.add(loan)
        self.db.commit()
        self.db.refresh(loan)
        
        return loan
    
    def get_loan(self, loan_id: int, user_id: int) -> Optional[PropertyLoan]:
        """
        Get a loan by ID with ownership validation.
        
        Args:
            loan_id: Loan ID
            user_id: User ID for ownership validation
            
        Returns:
            PropertyLoan instance or None if not found
        """
        return self.db.query(PropertyLoan).filter(
            PropertyLoan.id == loan_id,
            PropertyLoan.user_id == user_id
        ).first()
    
    def list_loans(
        self,
        user_id: int,
        property_id: Optional[UUID] = None
    ) -> List[PropertyLoan]:
        """
        List loans for a user, optionally filtered by property.
        
        Args:
            user_id: User ID
            property_id: Optional property ID to filter by
            
        Returns:
            List of PropertyLoan instances
        """
        query = self.db.query(PropertyLoan).filter(PropertyLoan.user_id == user_id)
        
        if property_id:
            query = query.filter(PropertyLoan.property_id == property_id)
        
        return query.order_by(PropertyLoan.start_date.desc()).all()
    
    def update_loan(
        self,
        loan_id: int,
        user_id: int,
        **updates
    ) -> PropertyLoan:
        """
        Update a loan.
        
        Args:
            loan_id: Loan ID
            user_id: User ID for ownership validation
            **updates: Fields to update
            
        Returns:
            Updated PropertyLoan instance
            
        Raises:
            ValueError: If loan not found or doesn't belong to user
        """
        loan = self.get_loan(loan_id, user_id)
        
        if not loan:
            raise ValueError("Loan not found or does not belong to user")
        
        # Update allowed fields
        allowed_fields = [
            'loan_amount', 'interest_rate', 'start_date', 'end_date',
            'monthly_payment', 'lender_name', 'lender_account',
            'loan_type', 'notes'
        ]
        
        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                setattr(loan, field, value)
        
        loan.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(loan)
        
        return loan
    
    def delete_loan(self, loan_id: int, user_id: int) -> bool:
        """
        Delete a loan.
        
        Args:
            loan_id: Loan ID
            user_id: User ID for ownership validation
            
        Returns:
            True if deleted, False if not found
        """
        loan = self.get_loan(loan_id, user_id)
        
        if not loan:
            return False
        
        self.db.delete(loan)
        self.db.commit()
        
        return True
    
    def generate_amortization_schedule(
        self,
        loan_id: int,
        user_id: int
    ) -> List[AmortizationScheduleEntry]:
        """
        Generate complete amortization schedule for a loan.
        
        Uses standard amortization formula to calculate principal/interest split
        for each payment.
        
        Args:
            loan_id: Loan ID
            user_id: User ID for ownership validation
            
        Returns:
            List of AmortizationScheduleEntry instances
            
        Raises:
            ValueError: If loan not found
        """
        loan = self.get_loan(loan_id, user_id)
        
        if not loan:
            raise ValueError("Loan not found or does not belong to user")
        
        schedule = []
        remaining_balance = loan.loan_amount
        monthly_rate = loan.interest_rate / Decimal(12)
        payment_date = loan.start_date
        payment_number = 1
        
        # Calculate until balance is paid off or end_date reached
        max_payments = 360  # 30 years max
        
        while remaining_balance > Decimal("0.01") and payment_number <= max_payments:
            # Check if we've reached end_date
            if loan.end_date and payment_date > loan.end_date:
                break
            
            # Calculate interest for this period
            interest_amount = (remaining_balance * monthly_rate).quantize(Decimal("0.01"))
            
            # Calculate principal payment
            principal_amount = loan.monthly_payment - interest_amount
            
            # Handle final payment (may be less than monthly_payment)
            if principal_amount > remaining_balance:
                principal_amount = remaining_balance
                payment_amount = principal_amount + interest_amount
            else:
                payment_amount = loan.monthly_payment
            
            # Update remaining balance
            remaining_balance = (remaining_balance - principal_amount).quantize(Decimal("0.01"))
            
            # Create schedule entry
            entry = AmortizationScheduleEntry(
                payment_number=payment_number,
                payment_date=payment_date,
                payment_amount=payment_amount,
                principal_amount=principal_amount,
                interest_amount=interest_amount,
                remaining_balance=remaining_balance
            )
            schedule.append(entry)
            
            # Move to next month
            payment_number += 1
            if payment_date.month == 12:
                payment_date = date(payment_date.year + 1, 1, payment_date.day)
            else:
                payment_date = date(payment_date.year, payment_date.month + 1, payment_date.day)
        
        return schedule
    
    def calculate_annual_interest(
        self,
        loan_id: int,
        user_id: int,
        year: int
    ) -> Decimal:
        """
        Calculate total interest paid in a specific year using amortization schedule.
        
        Args:
            loan_id: Loan ID
            user_id: User ID for ownership validation
            year: Tax year to calculate interest for
            
        Returns:
            Total interest paid in the year
            
        Raises:
            ValueError: If loan not found
        """
        schedule = self.generate_amortization_schedule(loan_id, user_id)
        
        total_interest = Decimal("0")
        
        for entry in schedule:
            if entry.payment_date.year == year:
                total_interest += entry.interest_amount
        
        return total_interest.quantize(Decimal("0.01"))
    
    def calculate_remaining_balance(
        self,
        loan_id: int,
        user_id: int,
        as_of_date: date
    ) -> Decimal:
        """
        Calculate remaining loan balance as of a specific date using amortization schedule.
        
        Args:
            loan_id: Loan ID
            user_id: User ID for ownership validation
            as_of_date: Date to calculate balance for
            
        Returns:
            Remaining balance
            
        Raises:
            ValueError: If loan not found
        """
        schedule = self.generate_amortization_schedule(loan_id, user_id)
        
        # Find the last payment before or on as_of_date
        for entry in reversed(schedule):
            if entry.payment_date <= as_of_date:
                return entry.remaining_balance
        
        # If no payments made yet, return original loan amount
        loan = self.get_loan(loan_id, user_id)
        return loan.loan_amount if loan else Decimal("0")
    
    def get_loan_summary(
        self,
        loan_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Get comprehensive loan summary including calculated metrics.
        
        Args:
            loan_id: Loan ID
            user_id: User ID for ownership validation
            
        Returns:
            Dictionary with loan details and calculated metrics
            
        Raises:
            ValueError: If loan not found
        """
        loan = self.get_loan(loan_id, user_id)
        
        if not loan:
            raise ValueError("Loan not found or does not belong to user")
        
        # Generate schedule for calculations
        schedule = self.generate_amortization_schedule(loan_id, user_id)
        
        # Calculate totals
        total_payments = sum(entry.payment_amount for entry in schedule)
        total_interest = sum(entry.interest_amount for entry in schedule)
        total_principal = sum(entry.principal_amount for entry in schedule)
        
        # Current balance
        current_balance = self.calculate_remaining_balance(loan_id, user_id, date.today())
        
        # Current year interest
        current_year = date.today().year
        current_year_interest = self.calculate_annual_interest(loan_id, user_id, current_year)
        
        return {
            "loan_id": loan.id,
            "property_id": str(loan.property_id),
            "loan_amount": float(loan.loan_amount),
            "interest_rate": float(loan.interest_rate),
            "monthly_payment": float(loan.monthly_payment),
            "start_date": loan.start_date.isoformat(),
            "end_date": loan.end_date.isoformat() if loan.end_date else None,
            "lender_name": loan.lender_name,
            "loan_type": loan.loan_type,
            "current_balance": float(current_balance),
            "total_payments": float(total_payments),
            "total_interest": float(total_interest),
            "total_principal": float(total_principal),
            "current_year_interest": float(current_year_interest),
            "number_of_payments": len(schedule),
            "payments_remaining": sum(1 for entry in schedule if entry.remaining_balance > 0)
        }
    
    def create_interest_payment_transaction(
        self,
        loan_id: int,
        user_id: int,
        payment_date: date,
        interest_amount: Decimal,
        description: Optional[str] = None
    ) -> Transaction:
        """
        Create a transaction for loan interest payment linked to the property.
        
        This method creates an expense transaction with category LOAN_INTEREST
        and links it to the property associated with the loan.
        
        Args:
            loan_id: Loan ID
            user_id: User ID for ownership validation
            payment_date: Date of the interest payment
            interest_amount: Amount of interest paid
            description: Optional description (auto-generated if not provided)
            
        Returns:
            Created Transaction instance
            
        Raises:
            ValueError: If loan not found or interest_amount is invalid
        """
        loan = self.get_loan(loan_id, user_id)
        
        if not loan:
            raise ValueError("Loan not found or does not belong to user")
        
        if interest_amount <= 0:
            raise ValueError("Interest amount must be greater than zero")
        
        # Auto-generate description if not provided
        if not description:
            description = f"Loan interest payment - {loan.lender_name} ({payment_date.strftime('%B %Y')})"
        
        # Create transaction
        transaction = Transaction(
            user_id=user_id,
            property_id=loan.property_id,
            type=TransactionType.EXPENSE,
            amount=interest_amount,
            transaction_date=payment_date,
            description=description,
            expense_category=ExpenseCategory.LOAN_INTEREST,
            is_deductible=True,
            is_system_generated=False,
            import_source="loan_service",
            classification_confidence=Decimal("1.0")
        )
        
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        
        return transaction
    
    def create_monthly_interest_transactions(
        self,
        loan_id: int,
        user_id: int,
        year: int,
        month: Optional[int] = None
    ) -> List[Transaction]:
        """
        Create interest payment transactions for a specific month or entire year.
        
        Uses the amortization schedule to determine the exact interest amount
        for each payment period.
        
        Args:
            loan_id: Loan ID
            user_id: User ID for ownership validation
            year: Year to create transactions for
            month: Optional month (1-12). If None, creates for entire year
            
        Returns:
            List of created Transaction instances
            
        Raises:
            ValueError: If loan not found or transactions already exist
        """
        loan = self.get_loan(loan_id, user_id)
        
        if not loan:
            raise ValueError("Loan not found or does not belong to user")
        
        # Generate amortization schedule
        schedule = self.generate_amortization_schedule(loan_id, user_id)
        
        # Filter schedule entries for the specified period
        entries_to_process = []
        for entry in schedule:
            if entry.payment_date.year == year:
                if month is None or entry.payment_date.month == month:
                    entries_to_process.append(entry)
        
        if not entries_to_process:
            raise ValueError(f"No loan payments found for the specified period")
        
        # Check for existing transactions to avoid duplicates
        existing_transactions = self.db.query(Transaction).filter(
            Transaction.property_id == loan.property_id,
            Transaction.expense_category == ExpenseCategory.LOAN_INTEREST,
            Transaction.import_source == "loan_service",
            extract('year', Transaction.transaction_date) == year
        )
        
        if month is not None:
            existing_transactions = existing_transactions.filter(
                extract('month', Transaction.transaction_date) == month
            )
        
        if existing_transactions.count() > 0:
            raise ValueError(
                f"Interest payment transactions already exist for this period. "
                f"Delete existing transactions before creating new ones."
            )
        
        # Create transactions
        created_transactions = []
        
        try:
            for entry in entries_to_process:
                if entry.interest_amount > 0:
                    description = (
                        f"Loan interest payment - {loan.lender_name} "
                        f"(Payment #{entry.payment_number}, {entry.payment_date.strftime('%B %Y')})"
                    )
                    
                    transaction = Transaction(
                        user_id=user_id,
                        property_id=loan.property_id,
                        type=TransactionType.EXPENSE,
                        amount=entry.interest_amount,
                        transaction_date=entry.payment_date,
                        description=description,
                        expense_category=ExpenseCategory.LOAN_INTEREST,
                        is_deductible=True,
                        is_system_generated=True,
                        import_source="loan_service",
                        classification_confidence=Decimal("1.0")
                    )
                    
                    self.db.add(transaction)
                    created_transactions.append(transaction)
            
            self.db.commit()
            
            # Refresh all transactions
            for transaction in created_transactions:
                self.db.refresh(transaction)
            
            return created_transactions
            
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Failed to create interest transactions: {str(e)}")
    
    def get_interest_transactions(
        self,
        loan_id: int,
        user_id: int,
        year: Optional[int] = None
    ) -> List[Transaction]:
        """
        Get all interest payment transactions for a loan.
        
        Args:
            loan_id: Loan ID
            user_id: User ID for ownership validation
            year: Optional year to filter by
            
        Returns:
            List of Transaction instances
            
        Raises:
            ValueError: If loan not found
        """
        loan = self.get_loan(loan_id, user_id)
        
        if not loan:
            raise ValueError("Loan not found or does not belong to user")
        
        query = self.db.query(Transaction).filter(
            Transaction.property_id == loan.property_id,
            Transaction.expense_category == ExpenseCategory.LOAN_INTEREST,
            Transaction.import_source == "loan_service"
        )
        
        if year is not None:
            query = query.filter(extract('year', Transaction.transaction_date) == year)
        
        return query.order_by(Transaction.transaction_date).all()
    
    def link_existing_transaction_to_loan(
        self,
        transaction_id: int,
        loan_id: int,
        user_id: int
    ) -> Transaction:
        """
        Link an existing transaction to a loan's property.
        
        Useful for manually entered loan interest payments that need to be
        associated with a specific loan/property.
        
        Args:
            transaction_id: Transaction ID to link
            loan_id: Loan ID to link to
            user_id: User ID for ownership validation
            
        Returns:
            Updated Transaction instance
            
        Raises:
            ValueError: If transaction or loan not found, or ownership mismatch
        """
        loan = self.get_loan(loan_id, user_id)
        
        if not loan:
            raise ValueError("Loan not found or does not belong to user")
        
        transaction = self.db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id
        ).first()
        
        if not transaction:
            raise ValueError("Transaction not found or does not belong to user")
        
        # Update transaction to link to loan's property
        transaction.property_id = loan.property_id
        
        # Set category to LOAN_INTEREST if not already set
        if transaction.expense_category != ExpenseCategory.LOAN_INTEREST:
            transaction.expense_category = ExpenseCategory.LOAN_INTEREST
        
        # Mark as deductible
        transaction.is_deductible = True
        
        transaction.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(transaction)
        
        return transaction
