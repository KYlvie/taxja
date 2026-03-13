"""
Unit tests for Saldenliste service – API endpoints and edge cases.

Feature: saldenliste-reports
Validates: Requirements 4.1, 4.2, 4.3, 4.5
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.transaction import (
    ExpenseCategory,
    IncomeCategory,
    Transaction,
    TransactionType,
)
from app.models.user import User, UserType
from app.services.saldenliste_service import (
    KONTENPLAN_EA,
    KONTENPLAN_GMBH,
    generate_periodensaldenliste,
    generate_saldenliste,
    get_account_plan,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_user(user_type: UserType = UserType.SELF_EMPLOYED, user_id: int = 1) -> User:
    """Create a lightweight mock User object."""
    user = MagicMock(spec=User)
    user.id = user_id
    user.name = "Test User"
    user.user_type = user_type
    return user


def _make_transaction(
    user_id: int,
    txn_type: TransactionType,
    amount: float,
    txn_date: date,
    income_category: IncomeCategory | None = None,
    expense_category: ExpenseCategory | None = None,
) -> MagicMock:
    """Create a mock Transaction with the required attributes."""
    txn = MagicMock(spec=Transaction)
    txn.user_id = user_id
    txn.type = txn_type
    txn.amount = Decimal(str(amount))
    txn.transaction_date = txn_date
    txn.income_category = income_category
    txn.expense_category = expense_category
    return txn


def _mock_db_returning(transactions: list) -> MagicMock:
    """Build a mock db session whose .query().filter().all() returns *transactions*."""
    db = MagicMock()
    query = MagicMock()
    db.query.return_value = query
    query.filter.return_value = query

    # The service calls .filter() twice for saldenliste (current + prior year)
    # and once for periodensaldenliste.  We use side_effect so successive
    # .all() calls can return different lists when needed.
    query.all.return_value = transactions
    return db


def _mock_db_with_yearly_data(
    current_year_txns: list, prior_year_txns: list
) -> MagicMock:
    """Build a mock db session that returns different data for two successive queries.

    generate_saldenliste queries current year first, then prior year.
    """
    db = MagicMock()
    query = MagicMock()
    db.query.return_value = query

    filter_mock = MagicMock()
    query.filter.return_value = filter_mock

    # First .all() → current year, second .all() → prior year
    filter_mock.all.side_effect = [current_year_txns, prior_year_txns]
    return db


# ── Test: Empty data year returns zero-value report (Req 4.5) ───────────


class TestEmptyYearReturnsZeroValues:
    """When a tax year has no transactions, both report types must return
    a complete structure with all amounts set to zero.

    Validates: Requirement 4.5
    """

    def test_saldenliste_empty_year_returns_zero_structure(self):
        """Saldenliste with no transactions returns all-zero balances."""
        user = _make_user(UserType.SELF_EMPLOYED)
        db = _mock_db_returning([])

        result = generate_saldenliste(db, user, 2026, "de")

        assert result["report_type"] == "saldenliste"
        assert result["tax_year"] == 2026
        assert result["comparison_year"] == 2025

        # Every account in every group should have zero saldos
        for group in result["groups"]:
            for acct in group["accounts"]:
                assert acct["current_saldo"] == 0.0
                assert acct["prior_saldo"] == 0.0
                assert acct["deviation_abs"] == 0.0
            assert group["subtotal_current"] == 0.0
            assert group["subtotal_prior"] == 0.0

        # Summary should be all zeros
        summary = result["summary"]
        for key in summary:
            assert summary[key] == 0.0, f"summary['{key}'] should be 0.0"

    def test_periodensaldenliste_empty_year_returns_zero_structure(self):
        """Periodensaldenliste with no transactions returns all-zero monthly data."""
        user = _make_user(UserType.GMBH)
        db = _mock_db_returning([])

        result = generate_periodensaldenliste(db, user, 2026, "de")

        assert result["report_type"] == "periodensaldenliste"
        assert result["tax_year"] == 2026

        # Every account should have 12 zero months and zero gesamt
        for group in result["groups"]:
            for acct in group["accounts"]:
                assert acct["months"] == [0.0] * 12
                assert acct["gesamt"] == 0.0
            assert group["subtotal_months"] == [0.0] * 12
            assert group["subtotal_gesamt"] == 0.0

        # Summary monthly arrays should all be zeros
        summary = result["summary"]
        for key in ("aktiva_months", "passiva_months", "ertrag_months",
                     "aufwand_months", "gewinn_verlust_months"):
            assert summary[key] == [0.0] * 12
        for key in ("aktiva_gesamt", "passiva_gesamt", "ertrag_gesamt",
                     "aufwand_gesamt", "gewinn_verlust_gesamt"):
            assert summary[key] == 0.0

    def test_saldenliste_empty_year_ea_user_has_only_kk4_and_kk7(self):
        """EA user empty report should only contain Kontenklasse 4 and 7 groups."""
        user = _make_user(UserType.EMPLOYEE)
        db = _mock_db_returning([])

        result = generate_saldenliste(db, user, 2026, "de")

        group_kks = {g["kontenklasse"] for g in result["groups"]}
        assert group_kks == {4, 7}

    def test_saldenliste_empty_year_gmbh_user_has_full_kontenklassen(self):
        """GmbH user empty report should contain Kontenklassen 0-9."""
        user = _make_user(UserType.GMBH)
        db = _mock_db_returning([])

        result = generate_saldenliste(db, user, 2026, "de")

        group_kks = {g["kontenklasse"] for g in result["groups"]}
        assert group_kks == set(range(10))


# ── Test: Language parameter switching (Req 4.1, 4.2, 8.1) ─────────────


class TestLanguageParameterSwitching:
    """The language parameter must switch account labels and group labels
    between 'de', 'en', and 'zh'.

    Validates: Requirements 4.1, 4.2, 4.3
    """

    def test_saldenliste_german_labels(self):
        """German language returns German labels."""
        user = _make_user(UserType.SELF_EMPLOYED)
        db = _mock_db_returning([])

        result = generate_saldenliste(db, user, 2026, "de")

        # Check a known group label
        kk4_group = next(g for g in result["groups"] if g["kontenklasse"] == 4)
        assert kk4_group["label"] == "Erträge"

        # Check a known account label (4000 = agriculture after 7-Einkunftsarten expansion)
        acct_4000 = next(a for a in kk4_group["accounts"] if a["konto"] == "4000")
        assert acct_4000["label"] == "Einkünfte aus Land- und Forstwirtschaft"

    def test_saldenliste_english_labels(self):
        """English language returns English labels."""
        user = _make_user(UserType.SELF_EMPLOYED)
        db = _mock_db_returning([])

        result = generate_saldenliste(db, user, 2026, "en")

        kk4_group = next(g for g in result["groups"] if g["kontenklasse"] == 4)
        assert kk4_group["label"] == "Income"

        acct_4000 = next(a for a in kk4_group["accounts"] if a["konto"] == "4000")
        assert acct_4000["label"] == "Agriculture and Forestry Income"

    def test_saldenliste_chinese_labels(self):
        """Chinese language returns Chinese labels."""
        user = _make_user(UserType.SELF_EMPLOYED)
        db = _mock_db_returning([])

        result = generate_saldenliste(db, user, 2026, "zh")

        kk4_group = next(g for g in result["groups"] if g["kontenklasse"] == 4)
        assert kk4_group["label"] == "收入"

        acct_4000 = next(a for a in kk4_group["accounts"] if a["konto"] == "4000")
        assert acct_4000["label"] == "农林业收入"

    def test_periodensaldenliste_language_switching(self):
        """Periodensaldenliste also respects the language parameter."""
        user = _make_user(UserType.SELF_EMPLOYED)
        db = _mock_db_returning([])

        for lang, expected_kk4_label in [("de", "Erträge"), ("en", "Income"), ("zh", "收入")]:
            result = generate_periodensaldenliste(db, user, 2026, lang)
            kk4_group = next(g for g in result["groups"] if g["kontenklasse"] == 4)
            assert kk4_group["label"] == expected_kk4_label, (
                f"Language '{lang}': expected '{expected_kk4_label}', got '{kk4_group['label']}'"
            )

    def test_invalid_language_defaults_to_german(self):
        """An invalid language code should default to German."""
        user = _make_user(UserType.SELF_EMPLOYED)
        db = _mock_db_returning([])

        result = generate_saldenliste(db, user, 2026, "fr")

        kk4_group = next(g for g in result["groups"] if g["kontenklasse"] == 4)
        assert kk4_group["label"] == "Erträge"


# ── Test: Report structure and metadata ──────────────────────────────────


class TestReportStructure:
    """Verify the report response structure contains all required fields.

    Validates: Requirements 4.1, 4.2
    """

    def test_saldenliste_has_required_top_level_fields(self):
        """Saldenliste response must contain all required top-level keys."""
        user = _make_user(UserType.SELF_EMPLOYED)
        db = _mock_db_returning([])

        result = generate_saldenliste(db, user, 2026, "de")

        required_keys = {
            "report_type", "tax_year", "comparison_year",
            "user_name", "user_type", "generated_at", "groups", "summary",
        }
        assert required_keys.issubset(result.keys())

    def test_periodensaldenliste_has_required_top_level_fields(self):
        """Periodensaldenliste response must contain all required top-level keys."""
        user = _make_user(UserType.GMBH)
        db = _mock_db_returning([])

        result = generate_periodensaldenliste(db, user, 2026, "de")

        required_keys = {
            "report_type", "tax_year",
            "user_name", "user_type", "generated_at", "groups", "summary",
        }
        assert required_keys.issubset(result.keys())

    def test_saldenliste_account_has_required_fields(self):
        """Each account in a Saldenliste group must have the expected keys."""
        user = _make_user(UserType.SELF_EMPLOYED)
        db = _mock_db_returning([])

        result = generate_saldenliste(db, user, 2026, "de")

        acct = result["groups"][0]["accounts"][0]
        required_keys = {
            "konto", "label", "current_saldo", "prior_saldo",
            "deviation_abs", "deviation_pct",
        }
        assert required_keys.issubset(acct.keys())

    def test_periodensaldenliste_account_has_required_fields(self):
        """Each account in a Periodensaldenliste group must have the expected keys."""
        user = _make_user(UserType.SELF_EMPLOYED)
        db = _mock_db_returning([])

        result = generate_periodensaldenliste(db, user, 2026, "de")

        acct = result["groups"][0]["accounts"][0]
        required_keys = {"konto", "label", "months", "gesamt"}
        assert required_keys.issubset(acct.keys())
        assert len(acct["months"]) == 12

    def test_saldenliste_summary_has_required_fields(self):
        """Saldenliste summary must contain all required keys."""
        user = _make_user(UserType.SELF_EMPLOYED)
        db = _mock_db_returning([])

        result = generate_saldenliste(db, user, 2026, "de")

        required_keys = {
            "aktiva_current", "aktiva_prior",
            "passiva_current", "passiva_prior",
            "ertrag_current", "ertrag_prior",
            "aufwand_current", "aufwand_prior",
            "gewinn_verlust_current", "gewinn_verlust_prior",
        }
        assert required_keys.issubset(result["summary"].keys())


# ── Test: Different user types ───────────────────────────────────────────


class TestUserTypeHandling:
    """Verify reports work correctly for all user types.

    Validates: Requirements 4.1, 4.2, 4.3
    """

    @pytest.mark.parametrize("user_type", list(UserType))
    def test_saldenliste_works_for_all_user_types(self, user_type: UserType):
        """generate_saldenliste should produce a valid report for every user type."""
        user = _make_user(user_type)
        db = _mock_db_returning([])

        result = generate_saldenliste(db, user, 2026, "de")

        assert result["report_type"] == "saldenliste"
        assert result["user_type"] == user_type.value
        assert len(result["groups"]) > 0

    @pytest.mark.parametrize("user_type", list(UserType))
    def test_periodensaldenliste_works_for_all_user_types(self, user_type: UserType):
        """generate_periodensaldenliste should produce a valid report for every user type."""
        user = _make_user(user_type)
        db = _mock_db_returning([])

        result = generate_periodensaldenliste(db, user, 2026, "de")

        assert result["report_type"] == "periodensaldenliste"
        assert result["user_type"] == user_type.value
        assert len(result["groups"]) > 0


# ── Test: API endpoint existence and auth (Req 4.1, 4.2, 4.3) ──────────


class TestAPIEndpointExistence:
    """Verify the API endpoints are registered and require authentication.

    Validates: Requirements 4.1, 4.2, 4.3
    """

    def test_saldenliste_endpoint_exists_in_router(self):
        """POST /saldenliste endpoint must be registered in the reports router."""
        from app.api.v1.endpoints.reports import router

        paths = [route.path for route in router.routes]
        assert "/saldenliste" in paths

    def test_periodensaldenliste_endpoint_exists_in_router(self):
        """POST /periodensaldenliste endpoint must be registered in the reports router."""
        from app.api.v1.endpoints.reports import router

        paths = [route.path for route in router.routes]
        assert "/periodensaldenliste" in paths

    def test_saldenliste_endpoint_is_post(self):
        """The saldenliste endpoint must accept POST method."""
        from app.api.v1.endpoints.reports import router

        for route in router.routes:
            if hasattr(route, "path") and route.path == "/saldenliste":
                assert "POST" in route.methods
                break
        else:
            pytest.fail("Saldenliste route not found")

    def test_periodensaldenliste_endpoint_is_post(self):
        """The periodensaldenliste endpoint must accept POST method."""
        from app.api.v1.endpoints.reports import router

        for route in router.routes:
            if hasattr(route, "path") and route.path == "/periodensaldenliste":
                assert "POST" in route.methods
                break
        else:
            pytest.fail("Periodensaldenliste route not found")

    def test_saldenliste_endpoint_requires_auth_dependency(self):
        """The saldenliste endpoint must depend on get_current_user for auth."""
        from app.api.v1.endpoints.reports import router
        from app.core.security import get_current_user

        for route in router.routes:
            if hasattr(route, "path") and route.path == "/saldenliste":
                dep_callables = [d.call for d in route.dependant.dependencies]
                assert get_current_user in dep_callables, (
                    "Saldenliste endpoint must require authentication via get_current_user"
                )
                break

    def test_periodensaldenliste_endpoint_requires_auth_dependency(self):
        """The periodensaldenliste endpoint must depend on get_current_user for auth."""
        from app.api.v1.endpoints.reports import router
        from app.core.security import get_current_user

        for route in router.routes:
            if hasattr(route, "path") and route.path == "/periodensaldenliste":
                dep_callables = [d.call for d in route.dependant.dependencies]
                assert get_current_user in dep_callables, (
                    "Periodensaldenliste endpoint must require authentication via get_current_user"
                )
                break


# ── Test: Deviation edge case – prior year zero (Req 2.5) ───────────────


class TestDeviationEdgeCases:
    """Verify deviation_pct is None when prior_saldo is zero.

    Validates: Requirement 4.5 (zero-value handling)
    """

    def test_zero_prior_saldo_yields_null_deviation_pct(self):
        """When prior year has no data, deviation_pct should be None for all accounts."""
        user = _make_user(UserType.SELF_EMPLOYED)
        db = _mock_db_returning([])

        result = generate_saldenliste(db, user, 2026, "de")

        for group in result["groups"]:
            for acct in group["accounts"]:
                assert acct["deviation_pct"] is None, (
                    f"Account {acct['konto']}: deviation_pct should be None "
                    f"when both current and prior are zero"
                )
