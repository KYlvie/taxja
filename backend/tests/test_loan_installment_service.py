from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.loan_installment import LoanInstallment, LoanInstallmentSource
from app.models.property import Property, PropertyStatus, PropertyType
from app.models.property_loan import PropertyLoan
from app.models.user import User, UserType
from app.services.loan_service import LoanService


def _create_user(db):
    user = User(
        email="loan-installments@example.com",
        name="Loan Installments User",
        password_hash="hashed-password",
        user_type=UserType.LANDLORD,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_property(db, user):
    property_record = Property(
        id=uuid4(),
        user_id=user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Installmentstrasse 1, 1010 Wien",
        street="Installmentstrasse 1",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2024, 1, 1),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        construction_year=1990,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE,
    )
    db.add(property_record)
    db.commit()
    db.refresh(property_record)
    return property_record


def _create_loan(db, user, property_record):
    loan = PropertyLoan(
        user_id=user.id,
        property_id=property_record.id,
        loan_amount=Decimal("280000.00"),
        interest_rate=Decimal("0.0325"),
        start_date=date(2026, 1, 1),
        monthly_payment=Decimal("1508.33"),
        lender_name="Erste Bank",
        loan_type="annuity",
    )
    db.add(loan)
    db.commit()
    db.refresh(loan)
    return loan


def test_generate_installment_plan_persists_estimated_breakdown(db):
    user = _create_user(db)
    property_record = _create_property(db, user)
    loan = _create_loan(db, user, property_record)
    service = LoanService(db)

    installments = service.generate_installment_plan(loan.id, user.id)

    assert installments
    first_installment = installments[0]
    assert first_installment.due_date == date(2026, 1, 1)
    assert first_installment.scheduled_payment == Decimal("1508.33")
    assert first_installment.interest_amount == Decimal("758.33")
    assert first_installment.principal_amount == Decimal("750.00")
    assert first_installment.remaining_balance_after == Decimal("279250.00")
    assert first_installment.tax_year == 2026
    assert first_installment.source == LoanInstallmentSource.ESTIMATED


def test_generate_installment_plan_keeps_manual_override_rows(db):
    user = _create_user(db)
    property_record = _create_property(db, user)
    loan = _create_loan(db, user, property_record)
    service = LoanService(db)

    manual_installment = LoanInstallment(
        loan_id=loan.id,
        user_id=user.id,
        due_date=date(2026, 1, 1),
        tax_year=2026,
        scheduled_payment=Decimal("1508.33"),
        principal_amount=Decimal("700.00"),
        interest_amount=Decimal("808.33"),
        remaining_balance_after=Decimal("279300.00"),
        source=LoanInstallmentSource.MANUAL,
    )
    db.add(manual_installment)
    db.commit()

    installments = service.generate_installment_plan(loan.id, user.id)
    january = next(
        installment for installment in installments if installment.due_date == date(2026, 1, 1)
    )

    assert january.source == LoanInstallmentSource.MANUAL
    assert january.interest_amount == Decimal("808.33")
    assert january.principal_amount == Decimal("700.00")


def test_apply_annual_interest_certificate_overrides_year_and_reflows_estimates(db):
    user = _create_user(db)
    property_record = _create_property(db, user)
    loan = _create_loan(db, user, property_record)
    service = LoanService(db)

    service.generate_installment_plan(loan.id, user.id)
    updated_year = service.apply_annual_interest_certificate(
        loan.id,
        user.id,
        2026,
        Decimal("7146.54"),
    )

    assert updated_year
    assert all(
        installment.source == LoanInstallmentSource.ZINSBESCHEINIGUNG
        for installment in updated_year
    )
    assert sum((installment.interest_amount for installment in updated_year), Decimal("0")) == Decimal("7146.54")

    january_2027 = next(
        installment
        for installment in service.list_installments(loan.id, user.id)
        if installment.due_date == date(2027, 1, 1)
    )
    assert january_2027.source == LoanInstallmentSource.ESTIMATED
    assert january_2027.remaining_balance_after > Decimal("0")
