from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from app.models.recurring_transaction import RecurrenceFrequency, RecurringTransactionType
from app.services.recurring_transaction_service import RecurringTransactionService


def test_standalone_loan_repayment_does_not_generate_expense_transactions():
    mock_db = MagicMock()
    service = RecurringTransactionService(mock_db)

    recurring = MagicMock()
    recurring.id = 7
    recurring.user_id = 1
    recurring.recurring_type = RecurringTransactionType.LOAN_REPAYMENT
    recurring.transaction_type = "expense"
    recurring.amount = Decimal("1508.33")
    recurring.property_id = None
    recurring.loan_id = None
    recurring.description = "Loan repayment - Erste Bank"
    recurring.frequency = RecurrenceFrequency.MONTHLY

    txn = service._generate_transaction_from_recurring(recurring, date(2026, 3, 21))

    assert txn is None
