"""Service for managing and generating recurring transactions"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.recurring_transaction import (
    RecurringTransaction,
    RecurrenceFrequency,
    RecurringTransactionType
)
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.property import Property, PropertyStatus
from app.models.property_loan import PropertyLoan


class RecurringTransactionService:
    """Service for managing recurring transactions"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_rental_income_recurring(
        self,
        user_id: int,
        property_id: str,
        monthly_rent: Decimal,
        start_date: date,
        end_date: Optional[date] = None,
        day_of_month: int = 1
    ) -> RecurringTransaction:
        """
        Create a recurring transaction for rental income.
        
        Args:
            user_id: User ID
            property_id: Property UUID
            monthly_rent: Monthly rental amount
            start_date: Start date for recurring transaction
            end_date: Optional end date (None = indefinite)
            day_of_month: Day of month to generate transaction (1-31)
            
        Returns:
            Created RecurringTransaction
        """
        property_obj = self.db.query(Property).filter(Property.id == property_id).first()
        if not property_obj:
            raise ValueError(f"Property {property_id} not found")
        
        recurring = RecurringTransaction(
            user_id=user_id,
            recurring_type=RecurringTransactionType.RENTAL_INCOME,
            property_id=property_id,
            description=f"Rental income - {property_obj.address}",
            amount=monthly_rent,
            transaction_type="income",
            category="rental_income",
            frequency=RecurrenceFrequency.MONTHLY,
            start_date=start_date,
            end_date=end_date,
            day_of_month=day_of_month,
            is_active=True,
            next_generation_date=start_date
        )
        
        self.db.add(recurring)
        self.db.commit()
        self.db.refresh(recurring)
        
        return recurring
    
    def create_loan_interest_recurring(
        self,
        user_id: int,
        loan_id: int,
        monthly_interest: Decimal,
        start_date: date,
        end_date: Optional[date] = None,
        day_of_month: int = 1
    ) -> RecurringTransaction:
        """
        Create a recurring transaction for loan interest payments.
        
        Args:
            user_id: User ID
            loan_id: PropertyLoan ID
            monthly_interest: Monthly interest amount
            start_date: Start date
            end_date: Optional end date
            day_of_month: Day of month to generate
            
        Returns:
            Created RecurringTransaction
        """
        loan = self.db.query(PropertyLoan).filter(PropertyLoan.id == loan_id).first()
        if not loan:
            raise ValueError(f"Loan {loan_id} not found")
        
        recurring = RecurringTransaction(
            user_id=user_id,
            recurring_type=RecurringTransactionType.LOAN_INTEREST,
            loan_id=loan_id,
            property_id=loan.property_id,
            description=f"Loan interest - {loan.lender_name}",
            amount=monthly_interest,
            transaction_type="expense",
            category="loan_interest",
            frequency=RecurrenceFrequency.MONTHLY,
            start_date=start_date,
            end_date=end_date,
            day_of_month=day_of_month,
            is_active=True,
            next_generation_date=start_date
        )
        
        self.db.add(recurring)
        self.db.commit()
        self.db.refresh(recurring)
        
        return recurring
    
    def pause_recurring_transaction(self, recurring_id: int) -> RecurringTransaction:
        """Pause a recurring transaction"""
        recurring = self.db.query(RecurringTransaction).filter(
            RecurringTransaction.id == recurring_id
        ).first()
        
        if not recurring:
            raise ValueError(f"Recurring transaction {recurring_id} not found")
        
        recurring.is_active = False
        recurring.paused_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(recurring)
        
        return recurring
    
    def resume_recurring_transaction(self, recurring_id: int) -> RecurringTransaction:
        """Resume a paused recurring transaction"""
        recurring = self.db.query(RecurringTransaction).filter(
            RecurringTransaction.id == recurring_id
        ).first()
        
        if not recurring:
            raise ValueError(f"Recurring transaction {recurring_id} not found")
        
        recurring.is_active = True
        recurring.paused_at = None
        
        # Recalculate next generation date
        if recurring.last_generated_date:
            recurring.next_generation_date = recurring.calculate_next_date(recurring.last_generated_date)
        else:
            recurring.next_generation_date = recurring.start_date
        
        self.db.commit()
        self.db.refresh(recurring)
        
        return recurring
    
    def stop_recurring_transaction(self, recurring_id: int, end_date: Optional[date] = None) -> RecurringTransaction:
        """
        Stop a recurring transaction by setting end date.
        
        Args:
            recurring_id: Recurring transaction ID
            end_date: End date (defaults to today)
            
        Returns:
            Updated RecurringTransaction
        """
        recurring = self.db.query(RecurringTransaction).filter(
            RecurringTransaction.id == recurring_id
        ).first()
        
        if not recurring:
            raise ValueError(f"Recurring transaction {recurring_id} not found")
        
        recurring.end_date = end_date or date.today()
        recurring.is_active = False
        
        self.db.commit()
        self.db.refresh(recurring)
        
        return recurring
    
    def generate_due_transactions(self, target_date: Optional[date] = None) -> List[Transaction]:
        """
        Generate all due recurring transactions up to target date.
        
        This should be called daily by a scheduled task (Celery beat).
        
        Args:
            target_date: Date to generate up to (defaults to today)
            
        Returns:
            List of generated transactions
        """
        if target_date is None:
            target_date = date.today()
        
        # Find all active recurring transactions that are due
        due_recurrings = self.db.query(RecurringTransaction).filter(
            and_(
                RecurringTransaction.is_active == True,
                RecurringTransaction.start_date <= target_date,
                RecurringTransaction.next_generation_date <= target_date
            )
        ).all()
        
        generated_transactions = []
        
        for recurring in due_recurrings:
            # Check if should generate
            if not recurring.should_generate_for_date(target_date):
                continue
            
            # Check if end date has passed
            if recurring.end_date and target_date > recurring.end_date:
                recurring.is_active = False
                continue
            
            # Generate transaction
            transaction = self._generate_transaction_from_recurring(recurring, target_date)
            generated_transactions.append(transaction)
            
            # Update recurring transaction
            recurring.last_generated_date = target_date
            recurring.next_generation_date = recurring.calculate_next_date(target_date)
        
        self.db.commit()
        
        return generated_transactions
    
    def _generate_transaction_from_recurring(
        self,
        recurring: RecurringTransaction,
        transaction_date: date
    ) -> Transaction:
        """Generate a transaction from a recurring transaction"""
        
        # Determine transaction type and category
        if recurring.transaction_type == "income":
            txn_type = TransactionType.INCOME
            income_category = IncomeCategory.RENTAL if recurring.recurring_type == RecurringTransactionType.RENTAL_INCOME else None
            expense_category = None
        else:
            txn_type = TransactionType.EXPENSE
            income_category = None
            expense_category = ExpenseCategory.LOAN_INTEREST if recurring.recurring_type == RecurringTransactionType.LOAN_INTEREST else ExpenseCategory.OTHER
        
        transaction = Transaction(
            user_id=recurring.user_id,
            transaction_type=txn_type,
            amount=recurring.amount,
            date=transaction_date,
            description=f"{recurring.description} (Auto-generated)",
            category=recurring.category,
            income_category=income_category,
            expense_category=expense_category,
            property_id=recurring.property_id,
            is_deductible=recurring.transaction_type == "expense",
            notes=f"Auto-generated from recurring transaction #{recurring.id}"
        )
        
        self.db.add(transaction)
        
        return transaction
    
    def auto_pause_for_sold_property(self, property_id: str) -> List[RecurringTransaction]:
        """
        Automatically pause all recurring transactions for a sold property.
        
        Args:
            property_id: Property UUID
            
        Returns:
            List of paused recurring transactions
        """
        recurrings = self.db.query(RecurringTransaction).filter(
            and_(
                RecurringTransaction.property_id == property_id,
                RecurringTransaction.is_active == True
            )
        ).all()
        
        paused = []
        for recurring in recurrings:
            recurring.is_active = False
            recurring.paused_at = datetime.utcnow()
            recurring.end_date = date.today()
            recurring.notes = (recurring.notes or "") + f" [Auto-paused: Property sold on {date.today()}]"
            paused.append(recurring)
        
        self.db.commit()
        
        return paused
    
    def get_user_recurring_transactions(
        self,
        user_id: int,
        active_only: bool = True
    ) -> List[RecurringTransaction]:
        """Get all recurring transactions for a user"""
        query = self.db.query(RecurringTransaction).filter(
            RecurringTransaction.user_id == user_id
        )
        
        if active_only:
            query = query.filter(RecurringTransaction.is_active == True)
        
        return query.order_by(RecurringTransaction.next_generation_date).all()
    
    def get_property_recurring_transactions(
        self,
        property_id: str,
        active_only: bool = True
    ) -> List[RecurringTransaction]:
        """Get all recurring transactions for a property"""
        query = self.db.query(RecurringTransaction).filter(
            RecurringTransaction.property_id == property_id
        )
        
        if active_only:
            query = query.filter(RecurringTransaction.is_active == True)
        
        return query.all()
