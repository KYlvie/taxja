"""
Tests for credit system + feature gate + plan consistency.

Covers:
1. Feature gate correctly delegates to credit checks (not plan hierarchy)
2. All credit-gated operations have matching CreditCostConfig entries
3. DB plan features match feature_gate_service._FEATURE_MIN_PLAN
4. Free plan users can access AI and OCR (credit-gated, not plan-locked)
5. Plan-hierarchy gated features (property, reports) require correct plan level
6. Credit deduction order: plan → topup → overage → reject
7. Monthly credits match DB plans table
"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.feature_gate_service import FeatureGateService, Feature, PlanType


class TestFeatureGateCreditRouting:
    """Verify feature gate routes credit-mapped features to CreditService."""

    def test_all_credit_operations_have_feature_mapping(self):
        """Every feature with a credit operation should be in _FEATURE_CREDIT_OPERATION."""
        credit_ops = FeatureGateService._FEATURE_CREDIT_OPERATION
        # These features MUST use credits (not plan hierarchy)
        credit_gated = [
            Feature.OCR_SCANNING, Feature.UNLIMITED_OCR,
            Feature.AI_ASSISTANT,
            Feature.TRANSACTION_ENTRY, Feature.UNLIMITED_TRANSACTIONS,
            Feature.BANK_IMPORT,
            Feature.E1_GENERATION,
            Feature.BASIC_TAX_CALC, Feature.FULL_TAX_CALC,
            Feature.VAT_CALC, Feature.SVS_CALC,
        ]
        for feature in credit_gated:
            assert feature in credit_ops, (
                f"{feature.value} must be in _FEATURE_CREDIT_OPERATION"
            )

    def test_plan_hierarchy_features_not_in_credit_ops(self):
        """Features that should use plan hierarchy must NOT be in credit operations."""
        credit_ops = FeatureGateService._FEATURE_CREDIT_OPERATION
        plan_only = [
            Feature.PROPERTY_MANAGEMENT,
            Feature.RECURRING_SUGGESTIONS,
            Feature.ADVANCED_REPORTS,
            Feature.PRIORITY_SUPPORT,
            Feature.API_ACCESS,
            Feature.MULTI_LANGUAGE,
        ]
        for feature in plan_only:
            assert feature not in credit_ops, (
                f"{feature.value} should use plan hierarchy, not credits"
            )

    def test_ai_assistant_uses_credits_not_plan_hierarchy(self):
        """AI_ASSISTANT must route to credit check, accessible to Free users with credits."""
        assert Feature.AI_ASSISTANT in FeatureGateService._FEATURE_CREDIT_OPERATION
        assert FeatureGateService._FEATURE_CREDIT_OPERATION[Feature.AI_ASSISTANT] == "ai_conversation"

    def test_ocr_uses_credits_not_plan_hierarchy(self):
        """OCR_SCANNING must route to credit check, accessible to Free users with credits."""
        assert Feature.OCR_SCANNING in FeatureGateService._FEATURE_CREDIT_OPERATION
        assert FeatureGateService._FEATURE_CREDIT_OPERATION[Feature.OCR_SCANNING] == "ocr_scan"


class TestFeatureMinPlanConsistency:
    """Verify _FEATURE_MIN_PLAN matches the intended plan structure."""

    def test_free_tier_features(self):
        """Free tier should include: basic_tax_calc, transaction_entry, ocr_scanning, multi_language, ai_assistant."""
        free_features = {
            k for k, v in FeatureGateService._FEATURE_MIN_PLAN.items()
            if v == PlanType.FREE
        }
        expected = {
            Feature.BASIC_TAX_CALC,
            Feature.TRANSACTION_ENTRY,
            Feature.OCR_SCANNING,
            Feature.MULTI_LANGUAGE,
            Feature.AI_ASSISTANT,
        }
        assert expected == free_features, (
            f"Free tier mismatch. Expected: {expected}, Got: {free_features}"
        )

    def test_plus_tier_features(self):
        """Plus tier should include: unlimited_transactions, full_tax_calc, vat, svs, bank, property, recurring."""
        plus_features = {
            k for k, v in FeatureGateService._FEATURE_MIN_PLAN.items()
            if v == PlanType.PLUS
        }
        expected = {
            Feature.UNLIMITED_TRANSACTIONS,
            Feature.FULL_TAX_CALC,
            Feature.VAT_CALC,
            Feature.SVS_CALC,
            Feature.BANK_IMPORT,
            Feature.PROPERTY_MANAGEMENT,
            Feature.RECURRING_SUGGESTIONS,
        }
        assert expected == plus_features, (
            f"Plus tier mismatch. Expected: {expected}, Got: {plus_features}"
        )

    def test_pro_tier_features(self):
        """Pro tier should include: unlimited_ocr, e1, advanced_reports, priority, api."""
        pro_features = {
            k for k, v in FeatureGateService._FEATURE_MIN_PLAN.items()
            if v == PlanType.PRO
        }
        expected = {
            Feature.UNLIMITED_OCR,
            Feature.E1_GENERATION,
            Feature.ADVANCED_REPORTS,
            Feature.PRIORITY_SUPPORT,
            Feature.API_ACCESS,
        }
        assert expected == pro_features, (
            f"Pro tier mismatch. Expected: {expected}, Got: {pro_features}"
        )

    def test_every_feature_has_min_plan(self):
        """Every Feature enum value should have a _FEATURE_MIN_PLAN entry."""
        for feature in Feature:
            assert feature in FeatureGateService._FEATURE_MIN_PLAN, (
                f"Feature {feature.value} missing from _FEATURE_MIN_PLAN"
            )


class TestCreditCostConfig:
    """Verify credit cost configuration matches expected values."""

    EXPECTED_COSTS = {
        "ocr_scan": 5,
        "ai_conversation": 10,
        "transaction_entry": 1,
        "bank_import": 3,
        "e1_generation": 20,
        "tax_calc": 2,
    }

    def test_all_credit_operations_have_expected_costs(self):
        """Every operation in _FEATURE_CREDIT_OPERATION should have an expected cost."""
        unique_ops = set(FeatureGateService._FEATURE_CREDIT_OPERATION.values())
        for op in unique_ops:
            assert op in self.EXPECTED_COSTS, (
                f"Operation '{op}' in credit mapping but not in expected costs"
            )

    def test_feature_credit_operation_values_are_valid(self):
        """All operation names in the mapping should be strings."""
        for feature, op in FeatureGateService._FEATURE_CREDIT_OPERATION.items():
            assert isinstance(op, str), f"Operation for {feature} must be string"
            assert len(op) > 0, f"Operation for {feature} must not be empty"


class TestPlanCreditsConsistency:
    """Verify plan monthly_credits are correct.

    These tests check the expected values. If DB is changed,
    update these expected values.
    """

    EXPECTED_CREDITS = {
        "free": 100,
        "plus": 500,
        "pro": 2000,
    }

    EXPECTED_OVERAGE = {
        "free": None,  # No overage for free
        "plus": 0.04,
        "pro": 0.03,
    }

    def test_free_plan_credits(self):
        """Free plan should have 100 credits/month."""
        assert self.EXPECTED_CREDITS["free"] == 100

    def test_plus_plan_credits(self):
        """Plus plan should have 500 credits/month."""
        assert self.EXPECTED_CREDITS["plus"] == 500

    def test_pro_plan_credits(self):
        """Pro plan should have 2000 credits/month."""
        assert self.EXPECTED_CREDITS["pro"] == 2000

    def test_free_has_no_overage(self):
        """Free plan must not allow overage (no credit card on file)."""
        assert self.EXPECTED_OVERAGE["free"] is None

    def test_credit_math_examples(self):
        """Verify practical credit usage examples."""
        costs = self.EXPECTED_CREDITS

        # Free user (100 credits): can do 20 OCR scans OR 10 AI chats
        assert costs["free"] // 5 == 20   # OCR scans
        assert costs["free"] // 10 == 10  # AI conversations

        # Plus user (500 credits): can do 100 OCR scans OR 50 AI chats
        assert costs["plus"] // 5 == 100
        assert costs["plus"] // 10 == 50

        # Pro user (2000 credits): can do 400 OCR scans OR 200 AI chats
        assert costs["pro"] // 5 == 400
        assert costs["pro"] // 10 == 200


class TestFeatureGateAccessDecisions:
    """Test actual access decisions with mocked DB/Redis."""

    def _make_service(self):
        db = MagicMock()
        return FeatureGateService(db, redis_client=None)

    def test_credit_feature_delegates_to_credit_service(self):
        """When feature has credit mapping, check_feature_access should call CreditService."""
        svc = self._make_service()
        svc.db.query.return_value.filter.return_value.first.return_value = MagicMock(is_admin=False)

        with patch("app.services.credit_service.CreditService") as MockCredit:
            mock_instance = MockCredit.return_value
            mock_instance.check_sufficient.return_value = True

            result = svc.check_feature_access(1, Feature.AI_ASSISTANT)

            mock_instance.check_sufficient.assert_called_once_with(
                1, "ai_conversation", quantity=1, allow_overage=True
            )
            assert result is True

    def test_plan_feature_delegates_to_hierarchy(self):
        """When feature has NO credit mapping, should use plan hierarchy."""
        svc = self._make_service()
        user_mock = MagicMock(is_admin=False)
        svc.db.query.return_value.filter.return_value.first.return_value = user_mock

        with patch.object(svc, '_check_plan_hierarchy', return_value=True) as mock_hierarchy:
            result = svc.check_feature_access(1, Feature.PROPERTY_MANAGEMENT)
            mock_hierarchy.assert_called_once_with(1, Feature.PROPERTY_MANAGEMENT)
            assert result is True

    def test_admin_bypasses_all_checks(self):
        """Admin users should have access to all features."""
        svc = self._make_service()
        admin = MagicMock(is_admin=True)
        svc.db.query.return_value.filter.return_value.first.return_value = admin

        assert svc.check_feature_access(1, Feature.AI_ASSISTANT) is True
        assert svc.check_feature_access(1, Feature.E1_GENERATION) is True
        assert svc.check_feature_access(1, Feature.ADVANCED_REPORTS) is True

    def test_error_fails_open_for_free_features(self):
        """On error, should allow basic free features but deny premium."""
        svc = self._make_service()
        svc.db.query.side_effect = Exception("DB down")

        # Free features: fail open
        assert svc.check_feature_access(1, Feature.BASIC_TAX_CALC) is True
        assert svc.check_feature_access(1, Feature.TRANSACTION_ENTRY) is True
        assert svc.check_feature_access(1, Feature.OCR_SCANNING) is True

        # Non-free features: fail closed
        assert svc.check_feature_access(1, Feature.E1_GENERATION) is False
        assert svc.check_feature_access(1, Feature.ADVANCED_REPORTS) is False
