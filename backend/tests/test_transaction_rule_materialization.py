from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.credit_balance import CreditBalance
from app.models.credit_cost_config import CreditCostConfig
from app.models.user import SelfEmployedType, User, UserType


def _ensure_credit_setup(db: Session) -> None:
    existing_cost = (
        db.query(CreditCostConfig)
        .filter(CreditCostConfig.operation == "transaction_entry")
        .first()
    )
    if existing_cost is None:
        db.add(
            CreditCostConfig(
                operation="transaction_entry",
                credit_cost=1,
                description="Test transaction entry cost",
                is_active=True,
            )
        )
        db.commit()


def _create_user(
    db: Session,
    *,
    email: str,
    user_type: UserType,
    business_type: str | None = None,
) -> User:
    _ensure_credit_setup(db)
    user = User(
        email=email,
        password_hash=get_password_hash("TestPassword123"),
        name="Rule Test User",
        user_type=user_type,
        business_type=business_type,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    db.add(
        CreditBalance(
            user_id=user.id,
            plan_balance=100,
            topup_balance=0,
            overage_enabled=False,
        )
    )
    db.commit()
    return user


def _auth_headers(user: User) -> dict:
    access_token = create_access_token(data={"sub": user.email})
    return {"Authorization": f"Bearer {access_token}"}


def _home_office_payload(amount: str) -> dict:
    return {
        "type": "expense",
        "amount": amount,
        "transaction_date": "2026-03-15",
        "description": "Home office days",
        "expense_category": "home_office",
    }


def _posting_line(data: dict, posting_type: str) -> dict:
    return next(li for li in data["line_items"] if li["posting_type"] == posting_type)


def test_create_marketing_transaction_materializes_percentage_rule(
    client: TestClient,
    db: Session,
):
    user = _create_user(
        db,
        email="freiberufler@example.com",
        user_type=UserType.SELF_EMPLOYED,
        business_type=SelfEmployedType.FREIBERUFLER.value,
    )

    response = client.post(
        "/api/v1/transactions",
        json={
            "type": "expense",
            "amount": "45.00",
            "transaction_date": "2026-03-15",
            "description": "Mandant dinner",
            "expense_category": "marketing",
        },
        headers=_auth_headers(user),
    )

    assert response.status_code == 201
    data = response.json()
    assert len(data["line_items"]) == 2

    expense_line = _posting_line(data, "expense")
    private_line = _posting_line(data, "private_use")

    assert Decimal(expense_line["amount"]) == Decimal("22.50")
    assert Decimal(private_line["amount"]) == Decimal("22.50")
    assert expense_line["allocation_source"] == "percentage_rule"
    assert private_line["allocation_source"] == "percentage_rule"
    assert expense_line["is_deductible"] is True
    assert private_line["is_deductible"] is False
    assert expense_line["category"] == "marketing"
    assert private_line["category"] == "marketing"


def test_create_home_office_transactions_materialize_yearly_cap(
    client: TestClient,
    db: Session,
):
    user = _create_user(
        db,
        email="employee-cap@example.com",
        user_type=UserType.EMPLOYEE,
    )
    headers = _auth_headers(user)

    first = client.post("/api/v1/transactions", json=_home_office_payload("200.00"), headers=headers)
    second = client.post("/api/v1/transactions", json=_home_office_payload("200.00"), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201

    first_data = first.json()
    second_data = second.json()

    assert len(first_data["line_items"]) == 1
    assert _posting_line(first_data, "expense")["allocation_source"] == "cap_rule"
    assert _posting_line(first_data, "expense")["rule_bucket"] == "home_office_annual_cap"

    assert len(second_data["line_items"]) == 2
    expense_line = _posting_line(second_data, "expense")
    private_line = _posting_line(second_data, "private_use")
    assert Decimal(expense_line["amount"]) == Decimal("100.00")
    assert Decimal(private_line["amount"]) == Decimal("100.00")
    assert expense_line["rule_bucket"] == "home_office_annual_cap"
    assert private_line["rule_bucket"] == "home_office_annual_cap"


def test_update_home_office_transaction_recomputes_remaining_cap(
    client: TestClient,
    db: Session,
):
    user = _create_user(
        db,
        email="employee-update@example.com",
        user_type=UserType.EMPLOYEE,
    )
    headers = _auth_headers(user)

    first = client.post("/api/v1/transactions", json=_home_office_payload("200.00"), headers=headers).json()
    second = client.post("/api/v1/transactions", json=_home_office_payload("200.00"), headers=headers).json()

    update_response = client.put(
        f"/api/v1/transactions/{first['id']}",
        json={"amount": "100.00"},
        headers=headers,
    )
    assert update_response.status_code == 200

    refreshed_second = client.get(f"/api/v1/transactions/{second['id']}", headers=headers)
    assert refreshed_second.status_code == 200
    second_data = refreshed_second.json()

    assert len(second_data["line_items"]) == 1
    expense_line = _posting_line(second_data, "expense")
    assert Decimal(expense_line["amount"]) == Decimal("200.00")
    assert expense_line["allocation_source"] == "cap_rule"


def test_delete_home_office_transaction_recomputes_remaining_cap(
    client: TestClient,
    db: Session,
):
    user = _create_user(
        db,
        email="employee-delete@example.com",
        user_type=UserType.EMPLOYEE,
    )
    headers = _auth_headers(user)

    first = client.post("/api/v1/transactions", json=_home_office_payload("200.00"), headers=headers).json()
    second = client.post("/api/v1/transactions", json=_home_office_payload("200.00"), headers=headers).json()

    delete_response = client.delete(f"/api/v1/transactions/{first['id']}", headers=headers)
    assert delete_response.status_code == 204

    refreshed_second = client.get(f"/api/v1/transactions/{second['id']}", headers=headers)
    assert refreshed_second.status_code == 200
    second_data = refreshed_second.json()

    assert len(second_data["line_items"]) == 1
    expense_line = _posting_line(second_data, "expense")
    assert Decimal(expense_line["amount"]) == Decimal("200.00")
    assert expense_line["rule_bucket"] == "home_office_annual_cap"
