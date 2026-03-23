from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.property import Property, PropertyStatus, PropertyType
from app.models.property_loan import PropertyLoan
from app.models.user import User, UserType
from app.services.loan_service import LoanService


@pytest.fixture
def test_user(db: Session) -> User:
    user = User(
        email="loan-endpoints@example.com",
        password_hash=get_password_hash("TestPassword123"),
        name="Loan Endpoint User",
        user_type=UserType.LANDLORD,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    access_token = create_access_token(data={"sub": test_user.email})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def test_property(db: Session, test_user: User) -> Property:
    property_record = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Loan API Gasse 1, 1010 Wien",
        street="Loan API Gasse 1",
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


@pytest.fixture
def test_loan(db: Session, test_user: User, test_property: Property) -> PropertyLoan:
    loan = PropertyLoan(
        user_id=test_user.id,
        property_id=test_property.id,
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


def test_get_loan_summary_endpoint(
    client: TestClient,
    auth_headers: dict,
    db: Session,
    test_user: User,
    test_loan: PropertyLoan,
):
    service = LoanService(db)
    service.generate_installment_plan(test_loan.id, test_user.id)

    response = client.get(
        f"/api/v1/loans/{test_loan.id}/summary",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["loan_id"] == test_loan.id
    assert data["lender_name"] == "Erste Bank"
    assert data["number_of_payments"] > 0
    assert data["current_balance"] < float(test_loan.loan_amount)


def test_list_loan_installments_endpoint(
    client: TestClient,
    auth_headers: dict,
    db: Session,
    test_user: User,
    test_loan: PropertyLoan,
):
    service = LoanService(db)
    service.generate_installment_plan(test_loan.id, test_user.id)

    response = client.get(
        f"/api/v1/loans/{test_loan.id}/installments?tax_year=2026",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["loan_id"] == test_loan.id
    assert data["tax_year"] == 2026
    assert data["total"] == 12
    assert data["installments"][0]["source"] == "estimated"
    assert Decimal(data["installments"][0]["interest_amount"]) == Decimal("758.33")


def test_apply_annual_interest_certificate_endpoint(
    client: TestClient,
    auth_headers: dict,
    db: Session,
    test_user: User,
    test_loan: PropertyLoan,
):
    service = LoanService(db)
    service.generate_installment_plan(test_loan.id, test_user.id)

    response = client.post(
        f"/api/v1/loans/{test_loan.id}/annual-interest-certificate",
        headers=auth_headers,
        json={
            "tax_year": 2026,
            "annual_interest_amount": "7146.54",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["loan_id"] == test_loan.id
    assert Decimal(data["annual_interest_amount"]) == Decimal("7146.54")
    assert data["installments_updated"] == 12
    assert all(item["source"] == "zinsbescheinigung" for item in data["installments"])
    assert sum(Decimal(item["interest_amount"]) for item in data["installments"]) == Decimal(
        "7146.54"
    )
