"""
Tests for remaining Claude Code audit fixes (#14, #11, #32).

Covers:
1. #14 — Rule classifier word-boundary matching for short keywords
2. #11 — Marginal tax rate lookup replaces hardcoded 30%
3. #32 — What-If uses actual user income instead of amount * 0.8
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# 1. #14 — Word-boundary matching for short keywords
# ---------------------------------------------------------------------------

class TestRuleClassifierWordBoundary:
    """Short keywords (< 5 chars) must use word-boundary matching."""

    def _classify_expense(self, description: str):
        from app.services.rule_based_classifier import RuleBasedClassifier
        txn = MagicMock()
        txn.description = description
        txn.type = MagicMock(value="expense")
        return RuleBasedClassifier().classify(txn)

    def _classify_income(self, description: str):
        from app.services.rule_based_classifier import RuleBasedClassifier
        txn = MagicMock()
        txn.description = description
        txn.type = MagicMock(value="income")
        return RuleBasedClassifier().classify(txn)

    # --- "drei" should match the telecom provider, not substrings ---

    def test_drei_matches_standalone(self):
        """'drei' as standalone word → telecom."""
        result = self._classify_expense("drei rechnung november")
        assert result.category == "telecom"

    def test_drei_no_match_in_dreieck(self):
        """'drei' should NOT match inside 'dreieck'."""
        result = self._classify_expense("dreieck geometrie set")
        assert result.category != "telecom"

    def test_drei_no_match_in_dreizehn(self):
        """'drei' should NOT match inside 'dreizehn'."""
        result = self._classify_expense("dreizehn stück")
        assert result.category != "telecom"

    # --- "a1" should match the telecom provider, not substrings ---

    def test_a1_matches_standalone(self):
        """'a1' as standalone word → telecom."""
        result = self._classify_expense("a1 mobilfunkrechnung")
        assert result.category == "telecom"

    def test_a1_no_match_in_sa1do(self):
        """'a1' should NOT match inside 'sa1do'."""
        result = self._classify_expense("sa1do check")
        assert result.category != "telecom"

    # --- "obi" should match the hardware store, not substrings ---

    def test_obi_matches_standalone(self):
        """'obi' as standalone word → maintenance."""
        result = self._classify_expense("obi baumarkt schrauben")
        assert result.category == "maintenance"

    def test_obi_no_match_in_mobilfunk(self):
        """'obi' should NOT match inside 'mobilfunk'."""
        result = self._classify_expense("mobilfunk vertrag")
        assert result.category != "maintenance"

    # --- "evn" should match the utility company, not substrings ---

    def test_evn_matches_standalone(self):
        """'evn' as standalone word → utilities."""
        result = self._classify_expense("evn strom abrechnung")
        assert result.category == "utilities"

    def test_evn_no_match_in_seven(self):
        """'evn' should NOT match inside 'seven'."""
        result = self._classify_expense("seven eleven einkauf")
        assert result.category != "utilities"

    # --- "gas" (short keyword in PRODUCT_KEYWORDS) ---

    def test_gas_matches_standalone(self):
        """'gas' as standalone word → utilities."""
        result = self._classify_expense("gas rechnung dezember")
        assert result.category == "utilities"

    def test_gas_no_match_in_gastronomie(self):
        """'gas' should NOT match inside 'gastronomie' (income keyword)."""
        # For expense classification, 'gas' in 'gastronomie' should not trigger
        result = self._classify_expense("gastronomie bedarf")
        assert result.category != "utilities"

    # --- Long keywords still work with plain substring matching ---

    def test_long_keyword_reiniger_still_matches(self):
        """'reiniger' (8 chars) should still match via substring."""
        result = self._classify_expense("glasreiniger spray")
        assert result.category == "maintenance"

    def test_long_keyword_versicherung_still_matches(self):
        """'versicherung' (13 chars) should still match via substring."""
        result = self._classify_expense("kfz versicherung 2026")
        assert result.category == "insurance"

    # --- Income keywords ---

    def test_income_kest_matches_standalone(self):
        """'kest' (4 chars) as standalone → capital_gains."""
        result = self._classify_income("kest abrechnung")
        assert result.category == "capital_gains"

    def test_income_rent_matches_standalone(self):
        """'rent' (4 chars) as standalone → rental."""
        result = self._classify_income("rent payment march")
        assert result.category == "rental"


# ---------------------------------------------------------------------------
# 2. #11 — Marginal tax rate lookup
# ---------------------------------------------------------------------------

class TestMarginalRateLookup:
    """_get_marginal_rate should return actual Austrian bracket rates."""

    def _make_service(self, tax_brackets=None):
        from app.services.savings_suggestion_service import SavingsSuggestionService

        svc = SavingsSuggestionService.__new__(SavingsSuggestionService)
        svc.db = MagicMock()
        svc.tax_engine = MagicMock()
        svc.deduction_calc = MagicMock()
        svc.flat_rate_comparator = MagicMock()

        if tax_brackets is None:
            # 2026 Austrian brackets
            tax_brackets = [
                {"lower": 0, "upper": 13539, "rate": 0},
                {"lower": 13539, "upper": 21992, "rate": 20},
                {"lower": 21992, "upper": 36458, "rate": 30},
                {"lower": 36458, "upper": 70365, "rate": 40},
                {"lower": 70365, "upper": 104859, "rate": 48},
                {"lower": 104859, "upper": 1000000, "rate": 50},
                {"lower": 1000000, "rate": 55},
            ]
        svc.tax_engine.tax_config = {"tax_brackets": tax_brackets}
        return svc

    def test_zero_income_returns_zero_rate(self):
        svc = self._make_service()
        assert svc._get_marginal_rate(Decimal("0")) == Decimal("0")

    def test_low_income_in_first_bracket(self):
        """Income €10,000 → 0% bracket."""
        svc = self._make_service()
        assert svc._get_marginal_rate(Decimal("10000")) == Decimal("0")

    def test_income_in_20_percent_bracket(self):
        """Income €20,000 → 20% bracket."""
        svc = self._make_service()
        assert svc._get_marginal_rate(Decimal("20000")) == Decimal("0.20")

    def test_income_in_30_percent_bracket(self):
        """Income €30,000 → 30% bracket."""
        svc = self._make_service()
        assert svc._get_marginal_rate(Decimal("30000")) == Decimal("0.30")

    def test_income_in_40_percent_bracket(self):
        """Income €50,000 → 40% bracket."""
        svc = self._make_service()
        assert svc._get_marginal_rate(Decimal("50000")) == Decimal("0.40")

    def test_income_in_48_percent_bracket(self):
        """Income €80,000 → 48% bracket."""
        svc = self._make_service()
        assert svc._get_marginal_rate(Decimal("80000")) == Decimal("0.48")

    def test_income_in_50_percent_bracket(self):
        """Income €200,000 → 50% bracket."""
        svc = self._make_service()
        assert svc._get_marginal_rate(Decimal("200000")) == Decimal("0.50")

    def test_income_in_55_percent_bracket(self):
        """Income €2,000,000 → 55% bracket."""
        svc = self._make_service()
        assert svc._get_marginal_rate(Decimal("2000000")) == Decimal("0.55")

    def test_fallback_when_no_brackets(self):
        """No brackets → fallback 30%."""
        svc = self._make_service(tax_brackets=[])
        svc.tax_engine.tax_config = {"tax_brackets": []}
        assert svc._get_marginal_rate(Decimal("50000")) == Decimal("0.30")

    def test_savings_use_marginal_rate_not_hardcoded(self):
        """Home office suggestion should use actual marginal rate, not 30%."""
        svc = self._make_service()
        user = MagicMock()
        user.user_type = MagicMock()
        user.user_type.__eq__ = lambda self, other: str(self) in [
            str(other), "UserType.EMPLOYEE", "UserType.SELF_EMPLOYED"
        ]
        # Simulate EMPLOYEE
        from app.models.user import UserType
        user.user_type = UserType.EMPLOYEE

        svc.deduction_calc.HOME_OFFICE_DEDUCTION = Decimal("300")

        # With 40% marginal rate (income ~€50k)
        result = svc._check_home_office_deduction(user, 2026, Decimal("0.40"))
        assert result is not None
        # 300 * 0.40 = 120, not 300 * 0.30 = 90
        assert result.potential_savings == Decimal("120.0") or result.potential_savings == Decimal("120.00")



# ---------------------------------------------------------------------------
# 3. #32 — What-If uses actual user income
# ---------------------------------------------------------------------------

class TestWhatIfActualIncome:
    """_handle_what_if should use actual income, not amount * 0.8."""

    def _make_orchestrator(self, actual_income=None):
        from app.services.ai_orchestrator import AIOrchestrator, IntentResult, UserIntent

        orch = AIOrchestrator.__new__(AIOrchestrator)
        orch.tools = MagicMock()
        orch.db = MagicMock()
        orch.user_id = 1
        orch.language = "de"

        # Mock run_what_if to capture args
        orch.tools.run_what_if = MagicMock(return_value={
            "base_income": 0,
            "scenario_income": 0,
            "base_tax": 0,
            "scenario_tax": 0,
            "tax_difference": 0,
            "year": 2026,
        })

        # Mock the DB query chain: db.query(...).filter(...).scalar()
        # MagicMock auto-chains, so query().filter() returns a new mock.
        # We need filter().scalar() to return actual_income.
        mock_chain = MagicMock()
        mock_chain.filter.return_value.scalar.return_value = actual_income
        orch.tools.db = MagicMock()
        orch.tools.db.query.return_value = mock_chain
        orch.tools.user_id = 1

        return orch, IntentResult, UserIntent

    def test_single_amount_uses_actual_income_as_base(self):
        """When user provides one amount, base should be actual income."""
        orch, IntentResult, UserIntent = self._make_orchestrator(actual_income=45000)

        intent = IntentResult(
            intent=UserIntent.WHAT_IF,
            confidence=Decimal("0.90"),
            params={"amount": 60000, "amounts": []},
        )

        with patch("app.services.ai_orchestrator._format_what_if", return_value="test"):
            result = orch._handle_what_if(intent, "was wäre wenn 60000", "de", [], 2026)

        # run_what_if should have been called with actual income as base
        call_args = orch.tools.run_what_if.call_args
        base_arg = call_args[0][0]
        scenario_arg = call_args[0][1]
        # base should be 45000 (actual income), not 60000 * 0.8 = 48000
        assert base_arg == 45000.0 or base_arg == 45000
        assert scenario_arg == 60000

    def test_single_amount_fallback_when_no_income(self):
        """When no actual income found, falls back to amount * 0.8."""
        orch, IntentResult, UserIntent = self._make_orchestrator(actual_income=0)

        intent = IntentResult(
            intent=UserIntent.WHAT_IF,
            confidence=Decimal("0.90"),
            params={"amount": 60000, "amounts": []},
        )

        with patch("app.services.ai_orchestrator._format_what_if", return_value="test"):
            result = orch._handle_what_if(intent, "was wäre wenn 60000", "de", [], 2026)

        call_args = orch.tools.run_what_if.call_args
        base_arg = call_args[0][0]
        # 0 is falsy, so falls back to amount * 0.8 = 48000
        assert base_arg == 48000.0 or base_arg == 48000

    def test_two_amounts_ignores_db_query(self):
        """When user provides two amounts, use them directly."""
        orch, IntentResult, UserIntent = self._make_orchestrator(actual_income=45000)

        intent = IntentResult(
            intent=UserIntent.WHAT_IF,
            confidence=Decimal("0.90"),
            params={"amount": None, "amounts": [40000, 60000]},
        )

        with patch("app.services.ai_orchestrator._format_what_if", return_value="test"):
            result = orch._handle_what_if(intent, "40000 vs 60000", "de", [], 2026)

        call_args = orch.tools.run_what_if.call_args
        assert call_args[0][0] == 40000
        assert call_args[0][1] == 60000

    def test_db_error_falls_back_gracefully(self):
        """If DB query fails, falls back to amount * 0.8."""
        orch, IntentResult, UserIntent = self._make_orchestrator()
        # Make DB query raise
        orch.tools.db.query.side_effect = Exception("DB error")

        intent = IntentResult(
            intent=UserIntent.WHAT_IF,
            confidence=Decimal("0.90"),
            params={"amount": 50000, "amounts": []},
        )

        with patch("app.services.ai_orchestrator._format_what_if", return_value="test"):
            result = orch._handle_what_if(intent, "was wäre wenn 50000", "de", [], 2026)

        call_args = orch.tools.run_what_if.call_args
        base_arg = call_args[0][0]
        # Fallback: 50000 * 0.8 = 40000
        assert base_arg == 40000.0 or base_arg == 40000


# ---------------------------------------------------------------------------
# 4. _keyword_matches helper unit tests
# ---------------------------------------------------------------------------

class TestKeywordMatchesHelper:
    """Direct tests for the _keyword_matches function."""

    def test_short_keyword_word_boundary(self):
        from app.services.rule_based_classifier import _keyword_matches
        # "gas" (3 chars) should use word boundary
        assert _keyword_matches("gas", "gas rechnung") is True
        assert _keyword_matches("gas", "gastronomie") is False

    def test_long_keyword_substring(self):
        from app.services.rule_based_classifier import _keyword_matches
        # "reiniger" (8 chars) should use plain substring
        assert _keyword_matches("reiniger", "glasreiniger") is True
        assert _keyword_matches("reiniger", "reiniger spray") is True

    def test_exact_boundary_length(self):
        from app.services.rule_based_classifier import _keyword_matches
        # 4 chars → word boundary
        assert _keyword_matches("biff", "biff spray") is True
        assert _keyword_matches("biff", "abiff") is False
        # 5 chars → substring
        assert _keyword_matches("honig", "bienenhonig") is True

    def test_special_regex_chars_escaped(self):
        from app.services.rule_based_classifier import _keyword_matches
        # "a1" contains no special chars but test with hypothetical
        assert _keyword_matches("a1", "a1 rechnung") is True
        assert _keyword_matches("a1", "ba1ance") is False
