from datetime import date
from decimal import Decimal

import pytest

from app.models.recurring_transaction import (
    RecurrenceFrequency,
    RecurringTransaction,
    RecurringTransactionType,
)
from app.models.transaction import (
    ExpenseCategory,
    IncomeCategory,
    Transaction,
    TransactionType,
)
from app.models.transaction_line_item import (
    LineItemAllocationSource,
    LineItemPostingType,
    TransactionLineItem,
)
from app.models.user import User, UserType
from app.services.bilanz_report_service import generate_bilanz_report
from app.services.ea_report_service import generate_ea_report
from app.services.saldenliste_service import (
    generate_periodensaldenliste,
    generate_saldenliste,
)


def _create_user(db, *, email: str, user_type: UserType) -> User:
    user = User(
        email=email,
        password_hash="test-hash",
        name="Report Test User",
        user_type=user_type,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_legacy_loan_repayment_recurring(
    db,
    *,
    user_id: int,
    start_date: date,
) -> RecurringTransaction:
    recurring = RecurringTransaction(
        user_id=user_id,
        recurring_type=RecurringTransactionType.LOAN_REPAYMENT,
        description="Legacy loan repayment",
        amount=Decimal("1508.33"),
        transaction_type=TransactionType.EXPENSE.value,
        category="loan_repayment",
        frequency=RecurrenceFrequency.MONTHLY,
        start_date=start_date,
        day_of_month=start_date.day,
    )
    db.add(recurring)
    db.commit()
    db.refresh(recurring)
    return recurring


def _add_transaction(
    db,
    *,
    user_id: int,
    txn_type: TransactionType,
    amount: str,
    txn_date: date,
    description: str,
    income_category: IncomeCategory | None = None,
    expense_category: ExpenseCategory | None = None,
    is_deductible: bool = False,
    source_recurring_id: int | None = None,
) -> Transaction:
    transaction = Transaction(
        user_id=user_id,
        type=txn_type,
        amount=Decimal(amount),
        transaction_date=txn_date,
        description=description,
        income_category=income_category,
        expense_category=expense_category,
        is_deductible=is_deductible,
        source_recurring_id=source_recurring_id,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def _add_line_item(
    db,
    *,
    transaction_id: int,
    description: str,
    amount: str,
    posting_type: LineItemPostingType,
    category: str | None = None,
    is_deductible: bool = False,
    quantity: int = 1,
    sort_order: int = 0,
) -> TransactionLineItem:
    line_item = TransactionLineItem(
        transaction_id=transaction_id,
        description=description,
        amount=Decimal(amount),
        quantity=quantity,
        posting_type=posting_type,
        allocation_source=LineItemAllocationSource.MANUAL,
        category=category,
        is_deductible=is_deductible,
        sort_order=sort_order,
        vat_recoverable_amount=Decimal("0.00"),
    )
    db.add(line_item)
    db.commit()
    db.refresh(line_item)
    return line_item


def _find_group_account(groups, konto: str) -> dict:
    for group in groups:
        for account in group["accounts"]:
            if account["konto"] == konto:
                return account
    raise AssertionError(f"Account {konto} not found")


def _find_bilanz_item(groups, label: str) -> dict:
    for group in groups:
        for item in group["items"]:
            if item["label"] == label:
                return item
    raise AssertionError(f"Bilanz item '{label}' not found")


def test_ea_report_excludes_legacy_loan_repayment_expenses(db):
    user = _create_user(db, email="ea-report@example.com", user_type=UserType.LANDLORD)
    recurring = _create_legacy_loan_repayment_recurring(
        db,
        user_id=user.id,
        start_date=date(2026, 1, 1),
    )

    _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.INCOME,
        amount="3200.00",
        txn_date=date(2026, 1, 5),
        description="Rental income",
        income_category=IncomeCategory.RENTAL,
    )
    _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.EXPENSE,
        amount="1508.33",
        txn_date=date(2026, 1, 20),
        description="Loan repayment - Erste Bank",
        expense_category=ExpenseCategory.OTHER,
        source_recurring_id=recurring.id,
    )
    _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.EXPENSE,
        amount="906.25",
        txn_date=date(2026, 1, 20),
        description="Loan interest - Erste Bank",
        expense_category=ExpenseCategory.LOAN_INTEREST,
        is_deductible=True,
    )

    report = generate_ea_report(db, user, 2026)

    assert report["summary"]["total_expenses"] == pytest.approx(906.25)
    assert report["summary"]["total_deductible"] == pytest.approx(906.25)
    assert report["transaction_count"] == 2

    expense_descriptions = [
        item["description"]
        for section in report["expense_sections"]
        for item in section["items"]
    ]
    assert expense_descriptions == ["Loan interest - Erste Bank"]


def test_bilanz_report_uses_liability_transactions_instead_of_interest_multiplier(db):
    user = _create_user(db, email="bilanz-report@example.com", user_type=UserType.GMBH)

    _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.LIABILITY_DRAWDOWN,
        amount="5000.00",
        txn_date=date(2026, 1, 3),
        description="Loan drawdown",
    )
    _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.LIABILITY_REPAYMENT,
        amount="602.08",
        txn_date=date(2026, 2, 3),
        description="Loan principal repayment",
    )
    _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.EXPENSE,
        amount="906.25",
        txn_date=date(2026, 2, 3),
        description="Loan interest",
        expense_category=ExpenseCategory.LOAN_INTEREST,
        is_deductible=True,
    )

    report = generate_bilanz_report(db, user, 2026, language="en")

    loans_item = _find_bilanz_item(report["bilanz"]["passiva"], "Loans and Borrowings")
    assert loans_item["amount"] == pytest.approx(4397.92)
    assert loans_item["amount"] != pytest.approx(9062.5)
    assert report["guv"]["total_expenses"] == pytest.approx(906.25)


def test_saldenliste_posts_principal_movements_to_loan_account_2800(db):
    user = _create_user(db, email="saldenliste@example.com", user_type=UserType.GMBH)

    _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.LIABILITY_DRAWDOWN,
        amount="5000.00",
        txn_date=date(2026, 1, 3),
        description="Loan drawdown",
    )
    _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.LIABILITY_REPAYMENT,
        amount="602.08",
        txn_date=date(2026, 2, 3),
        description="Loan principal repayment",
    )

    report = generate_saldenliste(db, user, 2026)

    loan_account = _find_group_account(report["groups"], "2800")
    assert loan_account["current_saldo"] == pytest.approx(4397.92)
    assert report["summary"]["passiva_current"] == pytest.approx(4397.92)


def test_periodensaldenliste_keeps_ea_expense_totals_free_of_legacy_principal(db):
    user = _create_user(db, email="perioden@example.com", user_type=UserType.SELF_EMPLOYED)
    recurring = _create_legacy_loan_repayment_recurring(
        db,
        user_id=user.id,
        start_date=date(2026, 3, 1),
    )

    _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.EXPENSE,
        amount="1508.33",
        txn_date=date(2026, 3, 15),
        description="Loan repayment - Legacy",
        expense_category=ExpenseCategory.OTHER,
        source_recurring_id=recurring.id,
    )
    _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.EXPENSE,
        amount="150.00",
        txn_date=date(2026, 3, 20),
        description="Office supplies",
        expense_category=ExpenseCategory.OFFICE_SUPPLIES,
        is_deductible=True,
    )

    report = generate_periodensaldenliste(db, user, 2026)

    office_account = _find_group_account(report["groups"], "7060")
    assert office_account["gesamt"] == pytest.approx(150.0)
    assert report["summary"]["aufwand_gesamt"] == pytest.approx(150.0)


def test_ea_report_includes_interest_line_from_liability_repayment_parent(db):
    user = _create_user(db, email="ea-lines@example.com", user_type=UserType.LANDLORD)

    _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.INCOME,
        amount="3200.00",
        txn_date=date(2026, 2, 5),
        description="Rental income",
        income_category=IncomeCategory.RENTAL,
    )
    loan_payment = _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.LIABILITY_REPAYMENT,
        amount="1508.33",
        txn_date=date(2026, 2, 20),
        description="Loan installment",
    )
    _add_line_item(
        db,
        transaction_id=loan_payment.id,
        description="Interest portion",
        amount="906.25",
        posting_type=LineItemPostingType.EXPENSE,
        category=ExpenseCategory.LOAN_INTEREST.value,
        is_deductible=True,
        sort_order=0,
    )
    _add_line_item(
        db,
        transaction_id=loan_payment.id,
        description="Principal portion",
        amount="602.08",
        posting_type=LineItemPostingType.LIABILITY_REPAYMENT,
        sort_order=1,
    )

    report = generate_ea_report(db, user, 2026)

    assert report["summary"]["total_expenses"] == pytest.approx(906.25)
    assert report["summary"]["total_deductible"] == pytest.approx(906.25)
    interest_account = _find_group_account(
        generate_saldenliste(db, user, 2026)["groups"],
        "7160",
    )
    assert interest_account["current_saldo"] == pytest.approx(906.25)


def test_bilanz_and_saldenliste_split_interest_and_principal_from_one_parent(db):
    user = _create_user(db, email="split-parent@example.com", user_type=UserType.GMBH)

    _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.LIABILITY_DRAWDOWN,
        amount="5000.00",
        txn_date=date(2026, 1, 3),
        description="Loan drawdown",
    )
    loan_payment = _add_transaction(
        db,
        user_id=user.id,
        txn_type=TransactionType.LIABILITY_REPAYMENT,
        amount="1508.33",
        txn_date=date(2026, 2, 3),
        description="Loan installment",
    )
    _add_line_item(
        db,
        transaction_id=loan_payment.id,
        description="Interest portion",
        amount="906.25",
        posting_type=LineItemPostingType.EXPENSE,
        category=ExpenseCategory.LOAN_INTEREST.value,
        is_deductible=True,
        sort_order=0,
    )
    _add_line_item(
        db,
        transaction_id=loan_payment.id,
        description="Principal portion",
        amount="602.08",
        posting_type=LineItemPostingType.LIABILITY_REPAYMENT,
        sort_order=1,
    )

    bilanz_report = generate_bilanz_report(db, user, 2026, language="en")
    loans_item = _find_bilanz_item(bilanz_report["bilanz"]["passiva"], "Loans and Borrowings")
    assert loans_item["amount"] == pytest.approx(4397.92)
    assert bilanz_report["guv"]["total_expenses"] == pytest.approx(906.25)

    saldenliste_report = generate_saldenliste(db, user, 2026)
    loan_account = _find_group_account(saldenliste_report["groups"], "2800")
    interest_account = _find_group_account(saldenliste_report["groups"], "8200")
    assert loan_account["current_saldo"] == pytest.approx(4397.92)
    assert interest_account["current_saldo"] == pytest.approx(906.25)
