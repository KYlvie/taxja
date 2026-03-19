"""End-to-end style user journeys aligned to the current API contracts."""

from unittest.mock import patch

from app.models.credit_balance import CreditBalance
from app.models.credit_cost_config import CreditCostConfig
from app.models.user import User


def _register_verify_login(client, email: str, password: str, name: str, user_type: str) -> str:
    with patch("app.api.v1.endpoints.auth.send_verification_email"), patch(
        "app.api.v1.endpoints.auth.generate_verification_token",
        return_value="journey-verify-token",
    ):
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "name": name,
                "user_type": user_type,
            },
        )
    assert register_response.status_code == 201

    with patch("app.api.v1.endpoints.auth.TrialService.activate_trial"):
        verify_response = client.post("/api/v1/auth/verify-email?token=journey-verify-token")
    assert verify_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def _seed_transaction_credits(db, email: str, balance: int = 20) -> User:
    user = db.query(User).filter(User.email == email).first()
    db.add(
        CreditCostConfig(
            operation="transaction_entry",
            credit_cost=1,
            description="Journey transaction entry cost",
            is_active=True,
        )
    )
    db.add(
        CreditBalance(
            user_id=user.id,
            plan_balance=balance,
            topup_balance=0,
            overage_enabled=False,
            overage_credits_used=0,
            has_unpaid_overage=False,
            unpaid_overage_periods=0,
        )
    )
    db.commit()
    return user


class TestCompleteUserJourneys:
    """Critical journeys using current auth/profile/transaction flows."""

    def test_self_employed_onboarding_and_transaction_year(self, client, db):
        token = _register_verify_login(
            client=client,
            email="freelancer@example.com",
            password="SecurePass123!",
            name="Maria Mueller",
            user_type="self_employed",
        )
        headers = {"Authorization": f"Bearer {token}"}
        user = _seed_transaction_credits(db, "freelancer@example.com", balance=10)

        profile_response = client.put(
            "/api/v1/users/profile",
            json={
                "business_type": "freiberufler",
                "business_name": "Mueller Consulting",
                "business_industry": "software",
                "vat_status": "regelbesteuert",
                "gewinnermittlungsart": "ea_rechnung",
                "address": "Hauptstrasse 123, 1010 Wien",
                "language": "de",
            },
            headers=headers,
        )
        assert profile_response.status_code == 200
        profile = profile_response.json()
        assert profile["business_name"] == "Mueller Consulting"
        assert profile["vat_status"] == "regelbesteuert"
        assert profile["gewinnermittlungsart"] == "ea_rechnung"
        assert profile["tax_profile_completeness"]["is_complete_for_asset_automation"] is True

        income_response = client.post(
            "/api/v1/transactions",
            json={
                "type": "income",
                "amount": 8500.00,
                "transaction_date": "2026-01-31",
                "description": "Consulting Project",
                "income_category": "self_employment",
            },
            headers=headers,
        )
        assert income_response.status_code == 201
        assert income_response.headers["X-Credits-Remaining"] == "9"

        expense_response = client.post(
            "/api/v1/transactions",
            json={
                "type": "expense",
                "amount": 450.00,
                "transaction_date": "2026-02-10",
                "description": "Office supplies",
                "expense_category": "office_supplies",
                "is_deductible": True,
                "deduction_reason": "Business expense",
            },
            headers=headers,
        )
        assert expense_response.status_code == 201
        assert expense_response.headers["X-Credits-Remaining"] == "8"

        transactions_response = client.get(
            "/api/v1/transactions?tax_year=2026",
            headers=headers,
        )
        assert transactions_response.status_code == 200
        transactions = transactions_response.json()
        assert transactions["total"] == 2
        assert {item["type"] for item in transactions["transactions"]} == {"income", "expense"}

        balance = db.query(CreditBalance).filter(CreditBalance.user_id == user.id).first()
        assert balance.plan_balance == 8

    def test_employee_profile_and_disclaimer_journey(self, client, db):
        token = _register_verify_login(
            client=client,
            email="employee@example.com",
            password="SecurePass123!",
            name="Hans Schmidt",
            user_type="employee",
        )
        headers = {"Authorization": f"Bearer {token}"}
        user = _seed_transaction_credits(db, "employee@example.com", balance=5)

        profile_response = client.put(
            "/api/v1/users/profile",
            json={
                "employer_mode": "regular",
                "employer_region": "wien",
                "commuting_distance_km": 45,
                "public_transport_available": True,
                "num_children": 2,
                "is_single_parent": False,
                "language": "de",
            },
            headers=headers,
        )
        assert profile_response.status_code == 200
        profile = profile_response.json()
        assert profile["employer_mode"] == "regular"
        assert profile["commuting_distance_km"] == 45
        assert profile["num_children"] == 2
        assert profile["tax_profile_completeness"]["is_complete_for_asset_automation"] is True

        disclaimer_response = client.post(
            "/api/v1/users/disclaimer/accept",
            headers=headers,
        )
        assert disclaimer_response.status_code == 200
        assert disclaimer_response.json()["accepted"] is True

        status_response = client.get(
            "/api/v1/users/disclaimer/status",
            headers=headers,
        )
        assert status_response.status_code == 200
        assert status_response.json()["accepted"] is True

        salary_response = client.post(
            "/api/v1/transactions",
            json={
                "type": "income",
                "amount": 42000.00,
                "transaction_date": "2026-03-01",
                "description": "Annual Salary",
                "income_category": "employment",
            },
            headers=headers,
        )
        assert salary_response.status_code == 201

        expense_response = client.post(
            "/api/v1/transactions",
            json={
                "type": "expense",
                "amount": 250.00,
                "transaction_date": "2026-02-15",
                "description": "Work materials",
                "expense_category": "education",
                "is_deductible": True,
                "deduction_reason": "Work-related materials",
            },
            headers=headers,
        )
        assert expense_response.status_code == 201

        deductible_only = client.get(
            "/api/v1/transactions?type=expense&is_deductible=true",
            headers=headers,
        )
        assert deductible_only.status_code == 200
        data = deductible_only.json()
        assert data["total"] == 1
        assert data["transactions"][0]["description"] == "Work materials"

        balance = db.query(CreditBalance).filter(CreditBalance.user_id == user.id).first()
        assert balance.plan_balance == 3
