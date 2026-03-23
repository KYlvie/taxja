from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.liability import Liability, LiabilitySourceType, LiabilityType
from app.models.property import Property, PropertyStatus, PropertyType
from app.models.property_loan import PropertyLoan
from app.models.recurring_transaction import RecurringTransaction, RecurringTransactionType
from app.models.transaction import Transaction, TransactionType
from app.models.user import User, UserType
from app.services.liability_service import LiabilityService


@pytest.fixture
def liability_user(db: Session) -> User:
    user = User(
        email="liability-endpoints@example.com",
        password_hash=get_password_hash("TestPassword123"),
        name="Liability Endpoint User",
        user_type=UserType.LANDLORD,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def liability_auth_headers(liability_user: User) -> dict:
    access_token = create_access_token(data={"sub": liability_user.email})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def liability_property(db: Session, liability_user: User) -> Property:
    property_record = Property(
        user_id=liability_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Liability Street 9, 1010 Wien",
        street="Liability Street 9",
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


def test_create_liability_endpoint_creates_opening_balance_and_recurring_plan(
    client: TestClient,
    db: Session,
    liability_user: User,
    liability_auth_headers: dict,
    liability_property: Property,
):
    response = client.post(
        "/api/v1/liabilities",
        headers=liability_auth_headers,
        json={
            "liability_type": "business_loan",
            "display_name": "Working capital loan",
            "currency": "eur",
            "lender_name": "Hausbank",
            "principal_amount": "15000.00",
            "outstanding_balance": "12000.00",
            "interest_rate": "4.25",
            "start_date": "2026-01-01",
            "end_date": "2027-12-31",
            "monthly_payment": "500.00",
            "tax_relevant": True,
            "tax_relevance_reason": "Business expansion financing",
            "report_category": "darlehen_und_kredite",
            "linked_property_id": str(liability_property.id),
            "notes": "Initial drawdown",
            "create_recurring_plan": True,
            "recurring_day_of_month": 5,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["display_name"] == "Working capital loan"
    assert data["currency"] == "EUR"
    assert data["liability_type"] == "business_loan"
    assert data["source_type"] == "manual"
    assert data["can_edit_directly"] is True
    assert data["can_deactivate_directly"] is True
    liability_id = data["id"]

    liability = db.query(Liability).filter(Liability.id == liability_id).first()
    assert liability is not None
    assert liability.tax_relevant is True
    assert liability.linked_property_id == liability_property.id

    opening_tx = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == liability_user.id,
            Transaction.liability_id == liability_id,
            Transaction.type == TransactionType.LIABILITY_DRAWDOWN,
        )
        .one()
    )
    assert opening_tx.amount == Decimal("12000.00")
    assert "Opening balance" in (opening_tx.description or "")

    recurring = (
        db.query(RecurringTransaction)
        .filter(
            RecurringTransaction.user_id == liability_user.id,
            RecurringTransaction.liability_id == liability_id,
            RecurringTransaction.recurring_type == RecurringTransactionType.LOAN_REPAYMENT,
        )
        .one()
    )
    assert recurring.loan_id is None
    assert recurring.day_of_month == 5
    assert recurring.amount == Decimal("500.00")


def test_get_list_and_summary_endpoints_include_synced_property_loan_liability(
    client: TestClient,
    db: Session,
    liability_user: User,
    liability_auth_headers: dict,
    liability_property: Property,
):
    loan = PropertyLoan(
        user_id=liability_user.id,
        property_id=liability_property.id,
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

    liability = LiabilityService(db).ensure_property_loan_liability(loan)
    db.commit()
    db.refresh(liability)

    list_response = client.get("/api/v1/liabilities", headers=liability_auth_headers)
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert list_data["total"] >= 1
    assert any(item["linked_loan_id"] == loan.id for item in list_data["items"])

    detail_response = client.get(f"/api/v1/liabilities/{liability.id}", headers=liability_auth_headers)
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert detail_data["linked_loan_id"] == loan.id
    assert detail_data["report_category"] == "darlehen_und_kredite"
    assert len(detail_data["related_transactions"]) >= 1

    summary_response = client.get("/api/v1/liabilities/summary", headers=liability_auth_headers)
    assert summary_response.status_code == 200
    summary_data = summary_response.json()
    assert Decimal(summary_data["total_assets"]) == Decimal("350000.00")
    assert Decimal(summary_data["total_liabilities"]) >= Decimal("280000.00")
    assert summary_data["active_liability_count"] >= 1


def test_update_and_soft_delete_liability_endpoint(
    client: TestClient,
    db: Session,
    liability_user: User,
    liability_auth_headers: dict,
):
    liability = LiabilityService(db).create_liability(
        liability_user.id,
        liability_type=LiabilityType.FAMILY_LOAN,
        display_name="Family bridge loan",
        currency="EUR",
        lender_name="Parents",
        principal_amount=Decimal("20000.00"),
        outstanding_balance=Decimal("4000.00"),
        start_date=date(2025, 1, 1),
        monthly_payment=Decimal("375.00"),
        tax_relevant=False,
        report_category=None,
        create_recurring_plan=True,
        recurring_day_of_month=10,
    )

    update_response = client.put(
        f"/api/v1/liabilities/{liability.id}",
        headers=liability_auth_headers,
        json={
            "display_name": "Family bridge loan updated",
            "tax_relevant": True,
            "tax_relevance_reason": "Now tied to business cash flow",
            "outstanding_balance": "3250.00",
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["display_name"] == "Family bridge loan updated"
    assert updated["tax_relevant"] is True
    assert Decimal(updated["outstanding_balance"]) == Decimal("3250.00")

    delete_response = client.delete(
        f"/api/v1/liabilities/{liability.id}",
        headers=liability_auth_headers,
    )
    assert delete_response.status_code == 200
    deleted = delete_response.json()
    assert deleted["is_active"] is False

    db.refresh(liability)
    assert liability.is_active is False
    assert all(recurring.is_active is False for recurring in liability.recurring_transactions)


def test_document_backed_liability_cannot_be_updated_or_deleted_directly(
    client: TestClient,
    db: Session,
    liability_user: User,
    liability_auth_headers: dict,
    liability_property: Property,
):
    loan = PropertyLoan(
        user_id=liability_user.id,
        property_id=liability_property.id,
        loan_amount=Decimal("180000.00"),
        interest_rate=Decimal("0.0290"),
        start_date=date(2025, 1, 1),
        monthly_payment=Decimal("820.00"),
        lender_name="Raiffeisen",
        loan_type="annuity",
        loan_contract_document_id=123,
    )
    db.add(loan)
    db.commit()
    db.refresh(loan)

    liability = LiabilityService(db).ensure_property_loan_liability(
        loan,
        source_document_id=123,
        source_type=LiabilitySourceType.DOCUMENT_CONFIRMED,
    )
    db.commit()
    db.refresh(liability)

    update_response = client.put(
        f"/api/v1/liabilities/{liability.id}",
        headers=liability_auth_headers,
        json={"display_name": "Should not update"},
    )
    assert update_response.status_code == 409
    assert "linked contract or loan" in update_response.json()["detail"]

    delete_response = client.delete(
        f"/api/v1/liabilities/{liability.id}",
        headers=liability_auth_headers,
    )
    assert delete_response.status_code == 409
    assert "linked contract or loan" in delete_response.json()["detail"]

    db.refresh(liability)
    assert liability.is_active is True
