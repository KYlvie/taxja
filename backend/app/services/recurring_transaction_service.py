"""Service for managing and generating recurring transactions"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.recurring_transaction import (
    RecurringTransaction,
    RecurrenceFrequency,
    RecurringTransactionType
)
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.core.transaction_enum_coercion import coerce_expense_category, coerce_income_category
from app.models.property import Property, PropertyStatus
from app.models.property_loan import PropertyLoan
from app.models.liability import Liability


class RecurringTransactionService:
    """Service for managing recurring transactions"""
    
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _build_generated_description(recurring: RecurringTransaction) -> str:
        """Build a stable description for generated child transactions."""
        return f"{recurring.description} (Auto-generated from recurring #{recurring.id})"

    @staticmethod
    def _generated_transaction_matcher(recurring_id: int):
        """Match both explicit and legacy recurring child links."""
        return or_(
            Transaction.source_recurring_id == recurring_id,
            Transaction.parent_recurring_id == recurring_id,
            Transaction.description.ilike(f"%recurring #{recurring_id}%"),
        )

    def _find_existing_generated_transaction(
        self,
        recurring: RecurringTransaction,
        transaction_date: date,
    ) -> Optional[Transaction]:
        """Find an already generated occurrence for the recurring template/date."""
        return self.db.query(Transaction).filter(
            Transaction.user_id == recurring.user_id,
            Transaction.transaction_date == transaction_date,
            Transaction.is_system_generated == True,
            self._generated_transaction_matcher(recurring.id),
        ).order_by(Transaction.id.desc()).first()
    
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
        If an active rental-income recurring already exists for the same property,
        return the existing one instead of creating a duplicate.
        
        Args:
            user_id: User ID
            property_id: Property UUID
            monthly_rent: Monthly rental amount
            start_date: Start date for recurring transaction
            end_date: Optional end date (None = indefinite)
            day_of_month: Day of month to generate transaction (1-31)
            
        Returns:
            Created or existing RecurringTransaction
        """
        property_obj = self.db.query(Property).filter(Property.id == property_id).first()
        if not property_obj:
            raise ValueError(f"Property {property_id} not found")

        # Dedup: reuse existing active rental-income recurring for same property
        existing = (
            self.db.query(RecurringTransaction)
            .filter(
                RecurringTransaction.user_id == user_id,
                RecurringTransaction.property_id == property_id,
                RecurringTransaction.recurring_type == RecurringTransactionType.RENTAL_INCOME,
                RecurringTransaction.is_active == True,  # noqa: E712
            )
            .first()
        )
        if existing:
            return existing

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
        day_of_month: int = 1,
        liability_id: Optional[int] = None,
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
            liability_id=liability_id,
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
    
    def create_insurance_premium_recurring(
        self,
        user_id: int,
        amount: Decimal,
        frequency: RecurrenceFrequency,
        start_date: date,
        description: str = "Insurance premium",
        end_date: Optional[date] = None,
        day_of_month: int = 1,
        source_document_id: Optional[int] = None,
    ) -> RecurringTransaction:
        """
        Create a recurring transaction for insurance premium payments.
        
        Args:
            user_id: User ID
            amount: Premium amount per period
            frequency: Payment frequency (monthly, quarterly, annually)
            start_date: Start date for recurring transaction
            description: Description text
            end_date: Optional end date (None = indefinite)
            day_of_month: Day of month to generate transaction (1-31)
            source_document_id: Optional source document ID
            
        Returns:
            Created RecurringTransaction
        """
        recurring = RecurringTransaction(
            user_id=user_id,
            recurring_type=RecurringTransactionType.INSURANCE_PREMIUM,
            description=description,
            amount=amount,
            transaction_type="expense",
            category="insurance",
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
            day_of_month=day_of_month,
            is_active=True,
            next_generation_date=start_date,
            source_document_id=source_document_id,
        )
        
        self.db.add(recurring)
        self.db.commit()
        self.db.refresh(recurring)
        
        return recurring

    def create_loan_repayment_recurring(
        self,
        user_id: int,
        monthly_payment: Decimal,
        start_date: date,
        description: str = "Loan repayment",
        end_date: Optional[date] = None,
        day_of_month: int = 1,
        source_document_id: Optional[int] = None,
        liability_id: Optional[int] = None,
    ) -> RecurringTransaction:
        """
        Create a recurring transaction for standalone loan repayments.
        For loans not associated with a property (car loans, personal loans, etc.).
        
        Args:
            user_id: User ID
            monthly_payment: Monthly repayment amount
            start_date: Start date for recurring transaction
            description: Description text
            end_date: Optional end date (None = indefinite)
            day_of_month: Day of month to generate transaction (1-31)
            source_document_id: Optional source document ID
            
        Returns:
            Created RecurringTransaction
        """
        recurring = RecurringTransaction(
            user_id=user_id,
            recurring_type=RecurringTransactionType.LOAN_REPAYMENT,
            liability_id=liability_id,
            description=description,
            amount=monthly_payment,
            transaction_type=TransactionType.LIABILITY_REPAYMENT.value,
            category="loan_repayment",
            frequency=RecurrenceFrequency.MONTHLY,
            start_date=start_date,
            end_date=end_date,
            day_of_month=day_of_month,
            is_active=True,
            next_generation_date=start_date,
            source_document_id=source_document_id,
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
        Stop a recurring transaction by setting end date and deleting future transactions.
        
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
        
        stop_date = end_date or date.today()
        recurring.end_date = stop_date
        recurring.is_active = False
        recurring.next_generation_date = None
        
        # Delete system-generated transactions after the stop date
        # Match by description pattern OR parent_recurring_id
        deleted = self.db.query(Transaction).filter(
            Transaction.user_id == recurring.user_id,
            Transaction.is_system_generated == True,
            Transaction.transaction_date > stop_date,
            self._generated_transaction_matcher(recurring.id),
        ).delete(synchronize_session="fetch")
        
        if deleted:
            import logging
            logging.getLogger(__name__).info(
                f"Stopped recurring #{recurring_id}: deleted {deleted} future transactions after {stop_date}"
            )
        
        self.db.commit()
        self.db.refresh(recurring)
        
        return recurring
    
    def generate_due_transactions(
        self,
        target_date: Optional[date] = None,
        user_id: Optional[int] = None,
    ) -> List[Transaction]:
        """
        Generate all due recurring transactions up to target date.

        Backfills ALL missed occurrences: if a monthly recurring transaction
        has next_generation_date=2024-01-01 and target_date=2026-03-14,
        it will generate a transaction for every missed month.

        This should be called daily by a scheduled task (Celery beat),
        and also triggered on dashboard load or manual API call.

        Args:
            target_date: Date to generate up to (defaults to today)
            user_id: Optional user scope for interactive generation requests

        Returns:
            List of generated transactions
        """
        if target_date is None:
            target_date = date.today()

        # Find all active recurring transactions that are due
        filters = [
            RecurringTransaction.is_active == True,
            RecurringTransaction.start_date <= target_date,
            RecurringTransaction.next_generation_date.isnot(None),
            RecurringTransaction.next_generation_date <= target_date,
        ]
        if user_id is not None:
            filters.append(RecurringTransaction.user_id == user_id)

        due_recurrings = self.db.query(RecurringTransaction).filter(and_(*filters)).all()

        generated_transactions = []
        state_changed = False
        expired_rental_props: dict = {}  # {(prop_id_str, user_id): (prop_id, user_id)}

        for recurring in due_recurrings:
            # Check if end date has passed entirely
            if recurring.end_date and target_date > recurring.end_date:
                # Still generate up to end_date, then deactivate
                effective_target = recurring.end_date
            else:
                effective_target = target_date

            # Loop: generate ALL missed occurrences up to effective_target
            # Safety limit to prevent infinite loops (max 120 = 10 years monthly)
            iterations = 0
            max_iterations = 120

            while (
                recurring.next_generation_date is not None
                and recurring.next_generation_date <= effective_target
                and iterations < max_iterations
            ):
                gen_date = recurring.next_generation_date

                existing_transaction = self._find_existing_generated_transaction(recurring, gen_date)
                if existing_transaction:
                    if existing_transaction.source_recurring_id != recurring.id:
                        existing_transaction.source_recurring_id = recurring.id
                        state_changed = True
                else:
                    transaction = self._generate_transaction_from_recurring(recurring, gen_date)
                    if transaction is not None:
                        generated_transactions.append(transaction)
                        state_changed = True

                # Advance to next occurrence
                recurring.last_generated_date = gen_date
                recurring.next_generation_date = recurring.calculate_next_date(gen_date)
                state_changed = True
                iterations += 1

            # Deactivate if end date has fully passed
            if recurring.end_date and target_date > recurring.end_date and recurring.is_active:
                recurring.is_active = False
                state_changed = True
                # Track rental contracts for property recalculation
                if (
                    recurring.property_id
                    and recurring.recurring_type == RecurringTransactionType.RENTAL_INCOME
                ):
                    _expired_key = (str(recurring.property_id), recurring.user_id)
                    expired_rental_props[_expired_key] = (
                        recurring.property_id,
                        recurring.user_id,
                    )

        if state_changed:
            self.db.commit()

        # Recalculate rental percentage for properties whose contracts just expired
        if expired_rental_props:
            from app.services.property_service import PropertyService
            import logging

            _logger = logging.getLogger(__name__)
            ps = PropertyService(self.db)
            for prop_id, uid in expired_rental_props.values():
                try:
                    ps.recalculate_rental_percentage(prop_id, uid)
                    _logger.info(
                        "Recalculated rental_percentage after contract expiry "
                        f"(property={prop_id}, user={uid})"
                    )
                except Exception as e:
                    _logger.warning(
                        f"Failed to recalculate rental_percentage for property "
                        f"{prop_id} after contract expiry: {e}"
                    )

        return generated_transactions
    
    def _generate_transaction_from_recurring(
        self,
        recurring: RecurringTransaction,
        transaction_date: date
    ) -> Optional[Transaction]:
        """Generate a transaction from a recurring transaction."""

        # Legacy standalone loan repayments were modeled as expenses, which
        # distorted both bookkeeping and tax reports. Keep the template for
        # reference, but stop generating expense transactions from it.
        if recurring.recurring_type == RecurringTransactionType.LOAN_REPAYMENT:
            return None

        # Determine transaction type and category
        if recurring.transaction_type == TransactionType.INCOME.value:
            txn_type = TransactionType.INCOME
            income_category = coerce_income_category(recurring.category)
            if income_category is None and recurring.recurring_type == RecurringTransactionType.RENTAL_INCOME:
                income_category = IncomeCategory.RENTAL
            expense_category = None
            is_deductible = False
        elif recurring.transaction_type == TransactionType.EXPENSE.value:
            txn_type = TransactionType.EXPENSE
            income_category = None
            # Map recurring type to expense category
            expense_category_map = {
                RecurringTransactionType.LOAN_INTEREST: ExpenseCategory.LOAN_INTEREST,
                RecurringTransactionType.INSURANCE_PREMIUM: ExpenseCategory.INSURANCE,
            }
            expense_category = coerce_expense_category(recurring.category) or expense_category_map.get(
                recurring.recurring_type, ExpenseCategory.OTHER
            )
            is_deductible = True
        else:
            txn_type = TransactionType(recurring.transaction_type)
            income_category = None
            expense_category = None
            is_deductible = False
        
        transaction = Transaction(
            user_id=recurring.user_id,
            type=txn_type,
            amount=recurring.amount,
            transaction_date=transaction_date,
            description=self._build_generated_description(recurring),
            income_category=income_category,
            expense_category=expense_category,
            property_id=recurring.property_id,
            liability_id=recurring.liability_id,
            is_deductible=is_deductible,
            is_system_generated=True,
            source_recurring_id=recurring.id,
        )
        
        self.db.add(transaction)
        
        return transaction
    
    def auto_pause_for_sold_property(self, property_id: str) -> List[RecurringTransaction]:
        """
        Automatically pause all recurring transactions for a sold property.
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

    def update_and_regenerate(
        self,
        recurring_id: int,
        user_id: int,
        update_data: Dict[str, Any],
        apply_from: Optional[date] = None,
    ) -> RecurringTransaction:
        """
        Update a recurring transaction template and regenerate future transactions.

        1. Update the recurring template fields
        2. Delete all system-generated transactions from apply_from onwards
        3. Regenerate transactions up to today based on new template values
        """
        recurring = self.db.query(RecurringTransaction).filter(
            RecurringTransaction.id == recurring_id,
            RecurringTransaction.user_id == user_id,
        ).first()
        if not recurring:
            raise ValueError(f"Recurring transaction {recurring_id} not found")

        # Apply updates to template
        for field, value in update_data.items():
            if value is not None and hasattr(recurring, field):
                setattr(recurring, field, value)

        # Determine the cutoff date
        cutoff = apply_from or date.today()

        # Delete future system-generated transactions linked to this recurring
        self.db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.is_system_generated == True,
            self._generated_transaction_matcher(recurring.id),
            Transaction.transaction_date >= cutoff,
        ).delete(synchronize_session="fetch")

        # Reset generation tracking to cutoff
        recurring.last_generated_date = cutoff - __import__("datetime").timedelta(days=1)
        recurring.next_generation_date = cutoff

        self.db.commit()

        # Regenerate up to today
        generated = self.generate_due_transactions(target_date=date.today(), user_id=user_id)

        self.db.refresh(recurring)
        return recurring

    def convert_transaction_to_recurring(
        self,
        transaction_id: int,
        user_id: int,
        frequency: str,
        start_date: date,
        end_date: Optional[date] = None,
        day_of_month: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> RecurringTransaction:
        """
        Convert a single transaction into a recurring transaction template.

        Creates a new RecurringTransaction based on the single transaction's data,
        then marks the original transaction as the first generated instance.
        """
        txn = self.db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        ).first()
        if not txn:
            raise ValueError(f"Transaction {transaction_id} not found")

        if txn.is_system_generated or txn.parent_recurring_id or txn.source_recurring_id:
            raise ValueError("Cannot convert a system-generated or recurring-child transaction")

        # Determine recurring type
        if txn.type == TransactionType.INCOME:
            rec_type = RecurringTransactionType.OTHER_INCOME
            category = txn.income_category.value if txn.income_category else "other_income"
        else:
            rec_type = RecurringTransactionType.OTHER_EXPENSE
            category = txn.expense_category.value if txn.expense_category else "other"

        # Map frequency string
        freq_map = {
            "monthly": RecurrenceFrequency.MONTHLY,
            "quarterly": RecurrenceFrequency.QUARTERLY,
            "annually": RecurrenceFrequency.ANNUALLY,
            "weekly": RecurrenceFrequency.WEEKLY,
            "biweekly": RecurrenceFrequency.BIWEEKLY,
        }
        freq = freq_map.get(frequency, RecurrenceFrequency.MONTHLY)

        recurring = RecurringTransaction(
            user_id=user_id,
            recurring_type=rec_type,
            property_id=txn.property_id,
            description=txn.description,
            amount=txn.amount,
            transaction_type=txn.type.value,
            category=category,
            frequency=freq,
            start_date=start_date,
            end_date=end_date,
            day_of_month=day_of_month or start_date.day,
            notes=notes,
            is_active=True,
            next_generation_date=start_date,
        )

        self.db.add(recurring)
        self.db.flush()

        # Mark original transaction as linked to this recurring
        txn.is_recurring = False
        txn.parent_recurring_id = None  # Keep it independent
        txn.source_recurring_id = None
        txn.is_system_generated = False

        self.db.commit()
        self.db.refresh(recurring)

        return recurring
    
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
