"""Tests for business-type-specific expense deductibility rules."""
import pytest
from unittest.mock import Mock, MagicMock

from app.models.user import SelfEmployedType
from app.services.business_deductibility_rules import (
    get_business_type_override,
    get_pauschalierung_type,
    BUSINESS_TYPE_CONTEXTS,
)
from app.services.deductibility_checker import DeductibilityChecker


# ── get_business_type_override ──

class TestBusinessTypeOverrides:
    def test_freiberufler_groceries_not_deductible(self):
        result = get_business_type_override("freiberufler", "groceries")
        assert result is not None
        assert result["is_deductible"] is False
        assert "Wareneinsatz" in result["reason"]

    def test_gewerbetreibende_groceries_deductible(self):
        result = get_business_type_override("gewerbetreibende", "groceries")
        assert result is not None
        assert result["is_deductible"] is True
        assert "Wareneinsatz" in result["reason"]

    def test_neue_selbstaendige_groceries_needs_ai(self):
        result = get_business_type_override("neue_selbstaendige", "groceries")
        assert result is not None
        assert result["is_deductible"] == "NEEDS_AI"

    def test_land_forstwirtschaft_groceries_deductible(self):
        result = get_business_type_override("land_forstwirtschaft", "groceries")
        assert result is not None
        assert result["is_deductible"] is True

    def test_freiberufler_marketing_50_pct(self):
        result = get_business_type_override("freiberufler", "marketing")
        assert result is not None
        assert result["is_deductible"] is True
        assert result["deductible_pct"] == 0.5

    def test_gewerbetreibende_marketing_50_pct(self):
        result = get_business_type_override("gewerbetreibende", "marketing")
        assert result is not None
        assert result["deductible_pct"] == 0.5

    def test_land_forstwirtschaft_marketing_no_limit(self):
        """Agricultural direct sales have no 50% limit."""
        result = get_business_type_override("land_forstwirtschaft", "marketing")
        assert result is not None
        assert result["deductible_pct"] is None

    def test_no_override_for_office_supplies(self):
        """office_supplies not in overrides → use base rules."""
        result = get_business_type_override("freiberufler", "office_supplies")
        assert result is None

    def test_no_override_for_unknown_business_type(self):
        result = get_business_type_override("unknown_type", "groceries")
        assert result is None

    def test_no_override_for_none_business_type(self):
        result = get_business_type_override(None, "groceries")
        assert result is None


# ── get_pauschalierung_type ──

class TestPauschalierungType:
    def test_freiberufler_consulting(self):
        assert get_pauschalierung_type("freiberufler") == "consulting"

    def test_neue_selbstaendige_consulting(self):
        assert get_pauschalierung_type("neue_selbstaendige") == "consulting"

    def test_gewerbetreibende_general(self):
        assert get_pauschalierung_type("gewerbetreibende") == "general"

    def test_land_forstwirtschaft_agriculture(self):
        assert get_pauschalierung_type("land_forstwirtschaft") == "agriculture"

    def test_none_defaults_general(self):
        assert get_pauschalierung_type(None) == "general"

    def test_unknown_defaults_general(self):
        assert get_pauschalierung_type("something") == "general"


# ── Integration with DeductibilityChecker ──

class TestDeductibilityCheckerIntegration:
    def setup_method(self):
        self.checker = DeductibilityChecker()

    def test_freiberufler_groceries_rejected(self):
        """Freiberufler (doctor, lawyer) cannot deduct groceries."""
        result = self.checker.check("groceries", "self_employed", business_type="freiberufler")
        assert result.is_deductible is False
        assert "Wareneinsatz" in result.reason

    def test_gewerbetreibende_groceries_accepted(self):
        """Gewerbetreibende (shop, restaurant) can deduct goods purchased."""
        result = self.checker.check("groceries", "self_employed", business_type="gewerbetreibende")
        assert result.is_deductible is True
        assert "Wareneinsatz" in result.reason

    def test_freiberufler_marketing_has_tip(self):
        """Freiberufler marketing should mention 50% limitation."""
        result = self.checker.check("marketing", "self_employed", business_type="freiberufler")
        assert result.is_deductible is True
        assert result.tax_tip is not None
        assert "50%" in result.tax_tip

    def test_no_business_type_falls_back_to_base(self):
        """Without business_type, self_employed groceries → NEEDS_AI → fallback deductible."""
        result = self.checker.check("groceries", "self_employed")
        # Without AI and no business_type, falls through to base rules → NEEDS_AI → fallback
        assert result.is_deductible is True  # business user fallback

    def test_employee_unaffected_by_business_type(self):
        """business_type is ignored for non-self-employed users."""
        result = self.checker.check("groceries", "employee", business_type="gewerbetreibende")
        assert result.is_deductible is False

    def test_mixed_with_business_type(self):
        """Mixed users can use business_type overrides."""
        result = self.checker.check("groceries", "mixed", business_type="gewerbetreibende")
        assert result.is_deductible is True

    def test_office_supplies_no_override(self):
        """Categories without override still use base rules."""
        result = self.checker.check("office_supplies", "self_employed", business_type="freiberufler")
        assert result.is_deductible is True  # base rule: Betriebsausgabe

    def test_svs_always_deductible(self):
        """SVS contributions deductible for all self-employed sub-types."""
        for bt in ["freiberufler", "gewerbetreibende", "neue_selbstaendige", "land_forstwirtschaft"]:
            result = self.checker.check("svs_contributions", "self_employed", business_type=bt)
            assert result.is_deductible is True, f"SVS should be deductible for {bt}"

    def test_user_override_takes_priority_over_base_rules(self):
        """A user-confirmed override should beat the generic deductibility rules."""
        self.checker._user_svc = MagicMock()
        self.checker._user_svc.lookup.return_value = Mock(
            is_deductible=True,
            reason="User confirmed this vehicle expense is business-related",
        )

        result = self.checker.check(
            "vehicle",
            "employee",
            description="OMV guest shuttle fuel",
            user_id=42,
        )

        assert result.is_deductible is True
        assert "business-related" in result.reason
        self.checker._user_svc.lookup.assert_called_once_with(
            user_id=42,
            description="OMV guest shuttle fuel",
            expense_category="vehicle",
        )


# ── Business type contexts ──

class TestBusinessTypeContexts:
    def test_all_types_have_context(self):
        for bt in SelfEmployedType:
            assert bt in BUSINESS_TYPE_CONTEXTS

    def test_contexts_have_trilingual_descriptions(self):
        for bt, ctx in BUSINESS_TYPE_CONTEXTS.items():
            assert "description_de" in ctx
            assert "description_en" in ctx
            assert "description_zh" in ctx
            assert "typical_expenses" in ctx
            assert len(ctx["typical_expenses"]) > 0
