"""Integration tests for current tax and dashboard API contracts.

These tests replace the legacy dashboard-era tax suite with contracts that
match the implemented endpoints and models:
- /api/v1/dashboard
- /api/v1/tax/calculate-refund
- /api/v1/tax/refund-estimate
- /api/v1/tax/simulate
- /api/v1/tax/flat-rate-compare
- /api/v1/tax/koest-vs-est
- /api/v1/tax/calculate-grest
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.cache import cache
from app.models.transaction import ExpenseCategory, IncomeCategory, Transaction, TransactionType
from app.models.user import User, UserType


def _get_user(db) -> User:
    return db.query(User).filter(User.email == "testuser@example.com").first()


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
    vat_rate: str | None = None,
    vat_amount: str | None = None,
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
        vat_rate=Decimal(vat_rate) if vat_rate is not None else None,
        vat_amount=Decimal(vat_amount) if vat_amount is not None else None,
    )
    db.add(transaction)
    db.flush()
    return transaction


@pytest.fixture
def dashboard_cache_disabled(monkeypatch):
    async def _get(*args, **kwargs):
        return None

    async def _set(*args, **kwargs):
        return False

    async def _delete_pattern(*args, **kwargs):
        return 0

    monkeypatch.setattr(cache, "get", _get)
    monkeypatch.setattr(cache, "set", _set)
    monkeypatch.setattr(cache, "delete_pattern", _delete_pattern)


class TestCurrentDashboardTaxContracts:
    """Current dashboard tax summary behavior."""

    @patch(
        "app.services.recurring_transaction_service.RecurringTransactionService.generate_due_transactions",
        return_value=[],
    )
    def test_dashboard_returns_camelcase_tax_summary_for_employee_income(
        self,
        _mock_generate_due,
        db,
        authenticated_client,
        dashboard_cache_disabled,
    ):
        user = _get_user(db)
        _add_transaction(
            db,
            user_id=user.id,
            txn_type=TransactionType.INCOME,
            amount="50000.00",
            txn_date=date(2026, 12, 31),
            description="Annual salary",
            income_category=IncomeCategory.EMPLOYMENT,
        )
        db.commit()

        response = authenticated_client.get("/api/v1/dashboard", params={"tax_year": 2026})

        assert response.status_code == 200
        data = response.json()

        assert Decimal(str(data["yearToDateIncome"])) == Decimal("50000.00")
        assert Decimal(str(data["yearToDateExpenses"])) == Decimal("0.00")
        assert Decimal(str(data["estimatedTax"])) == Decimal("11447.20")
        assert data["hasLohnzettel"] is True
        assert Decimal(str(data["withheldTax"])) == Decimal("15000.00")
        assert data["taxYear"] == 2026

    @patch(
        "app.services.recurring_transaction_service.RecurringTransactionService.generate_due_transactions",
        return_value=[],
    )
    def test_dashboard_filters_transactions_by_tax_year(
        self,
        _mock_generate_due,
        db,
        authenticated_client,
        dashboard_cache_disabled,
    ):
        user = _get_user(db)
        _add_transaction(
            db,
            user_id=user.id,
            txn_type=TransactionType.INCOME,
            amount="12000.00",
            txn_date=date(2025, 12, 31),
            description="Prior year salary",
            income_category=IncomeCategory.EMPLOYMENT,
        )
        _add_transaction(
            db,
            user_id=user.id,
            txn_type=TransactionType.INCOME,
            amount="36000.00",
            txn_date=date(2026, 12, 31),
            description="Current year salary",
            income_category=IncomeCategory.EMPLOYMENT,
        )
        _add_transaction(
            db,
            user_id=user.id,
            txn_type=TransactionType.EXPENSE,
            amount="1500.00",
            txn_date=date(2026, 2, 10),
            description="Office supplies",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
        )
        db.commit()

        response = authenticated_client.get("/api/v1/dashboard", params={"tax_year": 2026})

        assert response.status_code == 200
        data = response.json()
        assert Decimal(str(data["yearToDateIncome"])) == Decimal("36000.00")
        assert Decimal(str(data["yearToDateExpenses"])) == Decimal("1500.00")
        assert Decimal(str(data["netIncome"])) == Decimal("34500.00")


class TestEmployeeRefundEndpoints:
    """Current employee refund calculation contracts."""

    def test_calculate_refund_uses_commuting_and_home_office_profile(
        self,
        db,
        authenticated_client,
    ):
        user = _get_user(db)
        user.user_type = UserType.EMPLOYEE
        user.commuting_info = {
            "distance_km": 45,
            "public_transport_available": True,
        }
        user.telearbeit_days = 100
        user.family_info = {}
        db.commit()

        response = authenticated_client.post(
            "/api/v1/tax/calculate-refund",
            json={
                "lohnzettel": {
                    "gross_income": 42000.0,
                    "withheld_tax": 9500.0,
                    "withheld_svs": 6300.0,
                    "employer_name": "Test Company GmbH",
                    "tax_year": 2026,
                },
                "additional_deductions": {
                    "donations": 100.0,
                },
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["is_refund"] is True
        assert Decimal(str(data["refund_amount"])) > Decimal("0.00")
        assert Decimal(str(data["deductions_applied"]["pendlerpauschale"])) == Decimal("1356.00")
        assert Decimal(str(data["deductions_applied"]["telearbeit_pauschale"])) == Decimal("300.00")
        assert Decimal(str(data["tax_credits_applied"]["pendlereuro"])) == Decimal("270.00")
        assert "verkehrsabsetzbetrag" in data["tax_credits_applied"]

    def test_refund_estimate_without_income_returns_guidance(
        self,
        authenticated_client,
    ):
        response = authenticated_client.get(
            "/api/v1/tax/refund-estimate",
            params={"tax_year": 2026},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["confidence"] == "none"
        assert data["estimated_refund"] == 0.0
        assert "No income data available" in data["message"]
        assert data["suggestions"]


class TestTaxScenarioAndComparisonEndpoints:
    """Current tax simulator and comparison routes."""

    @patch("app.api.v1.endpoints.tax._classify_with_ai")
    @patch("app.api.v1.endpoints.tax.CreditService.check_and_deduct")
    def test_tax_simulate_returns_credit_header_and_current_classification_contract(
        self,
        mock_check_and_deduct,
        mock_classify,
        db,
        authenticated_client,
    ):
        user = _get_user(db)
        _add_transaction(
            db,
            user_id=user.id,
            txn_type=TransactionType.INCOME,
            amount="50000.00",
            txn_date=date(2026, 12, 31),
            description="Annual salary",
            income_category=IncomeCategory.EMPLOYMENT,
        )
        db.commit()

        mock_check_and_deduct.return_value = SimpleNamespace(
            balance_after=SimpleNamespace(available_without_overage=7)
        )
        mock_classify.return_value = {
            "category": "office_supplies",
            "category_type": "expense",
            "legal_basis": "Section 16 EStG",
            "is_deductible": True,
            "vat_rate": 0.20,
            "vat_note": "Standard VAT",
            "confidence": 0.92,
            "explanation": "A deductible office expense reduces taxable income.",
            "verified": True,
            "correction_note": None,
        }

        response = authenticated_client.post(
            "/api/v1/tax/simulate",
            json={
                "tax_year": 2026,
                "changeType": "add_expense",
                "amount": 1000.0,
                "description": "Laptop accessories",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert response.headers["X-Credits-Remaining"] == "7"
        assert data["scenario_type"] == "add_expense"
        assert data["simulatedTax"] < data["currentTax"]
        assert data["classification"]["category"] == "office_supplies"

    def test_flat_rate_compare_returns_current_eligibility_contract_for_self_employed(
        self,
        db,
        authenticated_client,
    ):
        user = _get_user(db)
        user.user_type = UserType.SELF_EMPLOYED
        db.commit()

        _add_transaction(
            db,
            user_id=user.id,
            txn_type=TransactionType.INCOME,
            amount="80000.00",
            txn_date=date(2026, 12, 31),
            description="Consulting revenue",
            income_category=IncomeCategory.SELF_EMPLOYMENT,
        )
        _add_transaction(
            db,
            user_id=user.id,
            txn_type=TransactionType.EXPENSE,
            amount="10000.00",
            txn_date=date(2026, 6, 30),
            description="Professional services",
            expense_category=ExpenseCategory.PROFESSIONAL_SERVICES,
            is_deductible=True,
        )
        db.commit()

        response = authenticated_client.get(
            "/api/v1/tax/flat-rate-compare",
            params={"tax_year": 2026},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["eligibility"]["isEligible"] is True
        assert data["eligibility"]["reason"] == "eligible"
        assert Decimal(str(data["actualAccounting"]["grossIncome"])) == Decimal("80000.00")
        assert Decimal(str(data["actualAccounting"]["deductibleExpenses"])) == Decimal("10000.00")
        expected_flat_rate = (
            Decimal(str(data["flatRate"]["flatRatePercentage"])) / Decimal("100")
        ) * Decimal("80000.00")
        assert Decimal(str(data["flatRate"]["flatRateDeduction"])) == expected_flat_rate
        assert "basicExemption" in data["flatRate"]
        assert Decimal(str(data["flatRate"]["basicExemption"])) >= Decimal("0.00")
        assert data["recommendation"] in {"actual", "flat_rate"}

    def test_koest_vs_est_returns_current_comparison_shape(
        self,
        db,
        authenticated_client,
    ):
        user = _get_user(db)
        user.user_type = UserType.GMBH
        db.commit()

        _add_transaction(
            db,
            user_id=user.id,
            txn_type=TransactionType.INCOME,
            amount="150000.00",
            txn_date=date(2026, 12, 31),
            description="Operating revenue",
            income_category=IncomeCategory.BUSINESS,
        )
        _add_transaction(
            db,
            user_id=user.id,
            txn_type=TransactionType.EXPENSE,
            amount="40000.00",
            txn_date=date(2026, 12, 31),
            description="Deductible expenses",
            expense_category=ExpenseCategory.PROFESSIONAL_SERVICES,
            is_deductible=True,
        )
        db.commit()

        response = authenticated_client.get(
            "/api/v1/tax/koest-vs-est",
            params={"tax_year": 2026},
        )

        assert response.status_code == 200
        data = response.json()
        assert Decimal(str(data["profit"])) == Decimal("110000.00")
        assert "gmbh" in data
        assert "einzelunternehmen" in data
        assert Decimal(str(data["gmbh"]["total_tax"])) > Decimal("0.00")
        assert Decimal(str(data["einzelunternehmen"]["total_tax"])) > Decimal("0.00")

    def test_calculate_grest_family_transfer_returns_tier_breakdown(
        self,
        authenticated_client,
    ):
        response = authenticated_client.post(
            "/api/v1/tax/calculate-grest",
            json={
                "grundstueckswert": 500000.0,
                "is_family_transfer": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_family_transfer"] is True
        assert Decimal(str(data["tax_amount"])) == Decimal("7750.00")
        assert Decimal(str(data["effective_rate"])) == Decimal("0.0155")
        assert len(data["tier_breakdown"]) == 3
