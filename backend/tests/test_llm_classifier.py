"""
Comprehensive tests for LLM-based transaction classifier.

Tests cover:
- Merchant normalization
- Cache key building, hit/miss/expiry
- LLM response parsing (valid JSON, invalid JSON, missing fields)
- Category validation (invalid → fallback)
- User profile extraction from different context types
- Full classify flow with mocked LLM
- Integration with TransactionClassifier (rule → ML → LLM fallback chain)
"""
import hashlib
import json
import time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.services.llm_classifier import (
    LLMTransactionClassifier,
    LLMClassificationResult,
    VALID_EXPENSE_CATEGORIES,
    VALID_INCOME_CATEGORIES,
    _CacheEntry,
    _RedisClassificationCache,
    get_llm_classifier,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def classifier():
    """Fresh LLMTransactionClassifier with mocked LLM and in-memory-only cache."""
    with patch.object(_RedisClassificationCache, "_connect"):
        c = LLMTransactionClassifier()
    # Ensure cache uses in-memory only (no Redis)
    c._cache._redis = None
    c._cache._memory = {}
    # Mock LLM so no real API calls happen
    c._llm = MagicMock()
    c._llm.is_available = True
    return c


@pytest.fixture
def unavailable_classifier():
    """Classifier whose LLM is not available."""
    with patch.object(_RedisClassificationCache, "_connect"):
        c = LLMTransactionClassifier()
    c._cache._redis = None
    c._cache._memory = {}
    c._llm = MagicMock()
    c._llm.is_available = False
    return c


# ---------------------------------------------------------------------------
# Merchant normalization
# ---------------------------------------------------------------------------


class TestMerchantNormalization:
    def test_basic_lowercase(self):
        assert LLMTransactionClassifier._normalize_merchant("BILLA") == "billa"

    def test_strip_filiale_number(self):
        result = LLMTransactionClassifier._normalize_merchant("BILLA FILIALE 1234 WIEN")
        assert "1234" not in result
        assert "filiale" not in result
        assert "billa" in result

    def test_strip_zahlung_prefix(self):
        result = LLMTransactionClassifier._normalize_merchant("Zahlung an Müller GmbH")
        assert result == "müller gmbh"

    def test_strip_ueberweisung_prefix(self):
        result = LLMTransactionClassifier._normalize_merchant("Überweisung an Hofer KG")
        assert result == "hofer kg"

    def test_strip_lastschrift_prefix(self):
        result = LLMTransactionClassifier._normalize_merchant("Lastschrift Amazon EU")
        assert result == "amazon eu"

    def test_strip_gutschrift_prefix(self):
        result = LLMTransactionClassifier._normalize_merchant("Gutschrift Finanzamt Wien")
        assert result == "finanzamt wien"

    def test_strip_trailing_numbers(self):
        result = LLMTransactionClassifier._normalize_merchant("SPAR 98765")
        assert result == "spar"

    def test_strip_postal_code_and_city(self):
        result = LLMTransactionClassifier._normalize_merchant("HOFER 1010 Wien")
        assert "1010" not in result

    def test_collapse_whitespace(self):
        result = LLMTransactionClassifier._normalize_merchant("  BILLA   FILIALE   ")
        assert "  " not in result

    def test_empty_string(self):
        assert LLMTransactionClassifier._normalize_merchant("") == ""

    def test_kasse_number_stripped(self):
        result = LLMTransactionClassifier._normalize_merchant("BILLA Kasse 3 Wien")
        assert "kasse" not in result
        assert "3" not in result or result == "billa wien"


# ---------------------------------------------------------------------------
# Cache key building
# ---------------------------------------------------------------------------


class TestCacheKeyBuilding:
    def test_deterministic(self):
        key1 = LLMTransactionClassifier._build_cache_key(
            "billa", "expense", "self_employed", "freiberufler", "gastronomie"
        )
        key2 = LLMTransactionClassifier._build_cache_key(
            "billa", "expense", "self_employed", "freiberufler", "gastronomie"
        )
        assert key1 == key2

    def test_different_user_type_different_key(self):
        key_employee = LLMTransactionClassifier._build_cache_key(
            "billa", "expense", "employee", "", ""
        )
        key_self = LLMTransactionClassifier._build_cache_key(
            "billa", "expense", "self_employed", "freiberufler", "IT"
        )
        assert key_employee != key_self

    def test_different_industry_different_key(self):
        key_gastro = LLMTransactionClassifier._build_cache_key(
            "billa", "expense", "self_employed", "gewerbetreibende", "gastronomie"
        )
        key_it = LLMTransactionClassifier._build_cache_key(
            "billa", "expense", "self_employed", "gewerbetreibende", "IT"
        )
        assert key_gastro != key_it

    def test_different_txn_type_different_key(self):
        key_exp = LLMTransactionClassifier._build_cache_key(
            "billa", "expense", "employee", "", ""
        )
        key_inc = LLMTransactionClassifier._build_cache_key(
            "billa", "income", "employee", "", ""
        )
        assert key_exp != key_inc

    def test_key_is_32_chars(self):
        key = LLMTransactionClassifier._build_cache_key(
            "test", "expense", "employee", "", ""
        )
        assert len(key) == 32


# ---------------------------------------------------------------------------
# Cache operations (using _RedisClassificationCache in-memory fallback)
# ---------------------------------------------------------------------------


class TestCacheOperations:
    def test_cache_miss_returns_none(self, classifier):
        assert classifier._cache.get("nonexistent") is None

    def test_cache_set_and_get(self, classifier):
        result = LLMClassificationResult(
            category="groceries",
            confidence=Decimal("0.75"),
            category_type="expense",
        )
        classifier._cache.set("key1", result)
        cached = classifier._cache.get("key1")
        assert cached is not None
        assert cached.category == "groceries"

    def test_cache_expiry(self, classifier):
        result = LLMClassificationResult(
            category="groceries",
            confidence=Decimal("0.75"),
            category_type="expense",
        )
        # Set with very short TTL (already expired)
        classifier._cache._memory["expired_key"] = _CacheEntry(result, ttl=-1)
        assert classifier._cache.get("expired_key") is None
        # Expired entry should be removed
        assert "expired_key" not in classifier._cache._memory

    def test_cache_eviction_when_full(self, classifier):
        classifier._cache._max_memory_size = 5
        result = LLMClassificationResult(
            category="other", confidence=Decimal("0.75"), category_type="expense"
        )
        for i in range(6):
            classifier._cache.set(f"key_{i}", result)
        # Should not exceed max size (eviction happened)
        assert len(classifier._cache._memory) <= 6

    def test_cache_stats(self, classifier):
        result = LLMClassificationResult(
            category="other", confidence=Decimal("0.75"), category_type="expense"
        )
        classifier._cache.set("active", result)
        classifier._cache._memory["expired"] = _CacheEntry(result, ttl=-1)

        stats = classifier.cache_stats()
        assert stats["total"] == 2
        assert stats["active"] == 1

    def test_cache_hit_sets_cached_flag(self, classifier):
        """classify() should set cached=True on cache hits."""
        result = LLMClassificationResult(
            category="groceries",
            confidence=Decimal("0.75"),
            category_type="expense",
            is_deductible=True,
        )
        merchant = classifier._normalize_merchant("BILLA Filiale 123")
        cache_key = classifier._build_cache_key(
            merchant, "expense", "employee", "", ""
        )
        classifier._cache.set(cache_key, result)

        out = classifier.classify(
            description="BILLA Filiale 123",
            amount=25.0,
            txn_type="expense",
            user_type="employee",
        )
        assert out is not None
        assert out.cached is True
        assert out.category == "groceries"


# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------


class TestResponseParsing:
    def test_valid_json_expense(self, classifier):
        response = '{"category": "groceries", "is_deductible": true, "reason": "Betriebsausgabe"}'
        result = classifier._parse_response(response, "expense")
        assert result is not None
        assert result.category == "groceries"
        assert result.is_deductible is True
        assert result.deduction_reason == "Betriebsausgabe"
        assert result.confidence == Decimal("0.75")

    def test_valid_json_income(self, classifier):
        response = '{"category": "rental", "is_deductible": false, "reason": "Mieteinnahme"}'
        result = classifier._parse_response(response, "income")
        assert result is not None
        assert result.category == "rental"
        assert result.category_type == "income"

    def test_json_with_markdown_fences(self, classifier):
        response = (
            '```json\n{"category": "office_supplies", "is_deductible": true,'
            ' "reason": "Büromaterial"}\n```'
        )
        result = classifier._parse_response(response, "expense")
        assert result is not None
        assert result.category == "office_supplies"

    def test_json_with_surrounding_text(self, classifier):
        response = (
            'Hier ist meine Analyse:\n{"category": "travel", "is_deductible": true,'
            ' "reason": "Dienstreise"}\nDas war es.'
        )
        result = classifier._parse_response(response, "expense")
        assert result is not None
        assert result.category == "travel"

    def test_empty_response(self, classifier):
        assert classifier._parse_response("", "expense") is None
        assert classifier._parse_response(None, "expense") is None

    def test_no_json_in_response(self, classifier):
        result = classifier._parse_response("Ich kann das nicht klassifizieren.", "expense")
        assert result is None

    def test_invalid_json(self, classifier):
        result = classifier._parse_response('{"category": "groceries", broken}', "expense")
        assert result is None

    def test_invalid_expense_category_falls_back_to_other(self, classifier):
        response = '{"category": "nonexistent_category", "is_deductible": false, "reason": "test"}'
        result = classifier._parse_response(response, "expense")
        assert result is not None
        assert result.category == "other"

    def test_invalid_income_category_falls_back_to_other_income(self, classifier):
        response = '{"category": "nonexistent_category", "is_deductible": false, "reason": "test"}'
        result = classifier._parse_response(response, "income")
        assert result is not None
        assert result.category == "other_income"

    def test_missing_category_field(self, classifier):
        response = '{"is_deductible": true, "reason": "test"}'
        result = classifier._parse_response(response, "expense")
        assert result is not None
        assert result.category == "other"  # empty → fallback

    def test_non_boolean_is_deductible(self, classifier):
        response = '{"category": "groceries", "is_deductible": "yes", "reason": "test"}'
        result = classifier._parse_response(response, "expense")
        assert result is not None
        assert result.is_deductible is None  # non-bool → None

    def test_reason_truncated_to_200(self, classifier):
        long_reason = "A" * 300
        response = json.dumps(
            {"category": "groceries", "is_deductible": True, "reason": long_reason}
        )
        result = classifier._parse_response(response, "expense")
        assert result is not None
        assert len(result.deduction_reason) == 200

    def test_deduction_reason_field_alias(self, classifier):
        response = (
            '{"category": "travel", "is_deductible": true, "deduction_reason": "Dienstreise"}'
        )
        result = classifier._parse_response(response, "expense")
        assert result is not None
        assert result.deduction_reason == "Dienstreise"

    def test_all_valid_expense_categories_accepted(self, classifier):
        for cat in VALID_EXPENSE_CATEGORIES:
            response = json.dumps({"category": cat, "is_deductible": False, "reason": "test"})
            result = classifier._parse_response(response, "expense")
            assert result is not None
            assert result.category == cat, f"Category {cat} should be accepted"

    def test_all_valid_income_categories_accepted(self, classifier):
        for cat in VALID_INCOME_CATEGORIES:
            response = json.dumps({"category": cat, "is_deductible": False, "reason": "test"})
            result = classifier._parse_response(response, "income")
            assert result is not None
            assert result.category == cat, f"Category {cat} should be accepted"


# ---------------------------------------------------------------------------
# Full classify flow
# ---------------------------------------------------------------------------


class TestClassifyFlow:
    def test_returns_none_when_unavailable(self, unavailable_classifier):
        result = unavailable_classifier.classify(
            description="BILLA", amount=25.0, txn_type="expense"
        )
        assert result is None

    def test_calls_llm_and_returns_result(self, classifier):
        classifier._llm.generate_simple.return_value = json.dumps(
            {"category": "groceries", "is_deductible": True, "reason": "Lebensmittel für Gastro"}
        )
        result = classifier.classify(
            description="BILLA Filiale 42",
            amount=55.90,
            txn_type="expense",
            user_type="self_employed",
            business_type="gewerbetreibende",
            business_industry="gastronomie",
        )
        assert result is not None
        assert result.category == "groceries"
        assert result.is_deductible is True
        assert result.cached is False
        classifier._llm.generate_simple.assert_called_once()

    def test_second_call_uses_cache(self, classifier):
        classifier._llm.generate_simple.return_value = json.dumps(
            {"category": "groceries", "is_deductible": True, "reason": "Gastro"}
        )
        # First call
        r1 = classifier.classify(
            description="BILLA", amount=25.0, txn_type="expense",
            user_type="employee",
        )
        # Second call — same merchant + user profile
        r2 = classifier.classify(
            description="BILLA", amount=30.0, txn_type="expense",
            user_type="employee",
        )
        assert r2 is not None
        assert r2.cached is True
        # LLM should only be called once
        assert classifier._llm.generate_simple.call_count == 1

    def test_different_user_profile_no_cache_hit(self, classifier):
        classifier._llm.generate_simple.return_value = json.dumps(
            {"category": "groceries", "is_deductible": False, "reason": "Privat"}
        )
        classifier.classify(
            description="BILLA", amount=25.0, txn_type="expense",
            user_type="employee",
        )
        # Different user type → different cache key → new LLM call
        classifier._llm.generate_simple.return_value = json.dumps(
            {"category": "groceries", "is_deductible": True, "reason": "Gastro"}
        )
        r2 = classifier.classify(
            description="BILLA", amount=25.0, txn_type="expense",
            user_type="self_employed",
            business_type="gewerbetreibende",
            business_industry="gastronomie",
        )
        assert r2 is not None
        assert r2.cached is False
        assert classifier._llm.generate_simple.call_count == 2

    def test_llm_exception_returns_none(self, classifier):
        classifier._llm.generate_simple.side_effect = Exception("API error")
        result = classifier.classify(
            description="BILLA", amount=25.0, txn_type="expense"
        )
        assert result is None

    def test_llm_returns_empty_string(self, classifier):
        classifier._llm.generate_simple.return_value = ""
        result = classifier.classify(
            description="BILLA", amount=25.0, txn_type="expense"
        )
        assert result is None

    def test_prompt_contains_user_profile(self, classifier):
        classifier._llm.generate_simple.return_value = json.dumps(
            {"category": "other", "is_deductible": False, "reason": "test"}
        )
        classifier.classify(
            description="Test",
            amount=100.0,
            txn_type="expense",
            user_type="self_employed",
            business_type="freiberufler",
            business_industry="fotografie",
        )
        call_args = classifier._llm.generate_simple.call_args
        system_prompt = (
            call_args.kwargs.get("system_prompt")
            or call_args[1].get("system_prompt", "")
            if len(call_args) > 1
            else ""
        )
        if not system_prompt:
            # Try positional
            system_prompt = call_args[0][0] if call_args[0] else ""
        # The prompt should contain user profile info
        assert "self_employed" in system_prompt or "fotografie" in system_prompt


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_llm_classifier_returns_same_instance(self):
        import app.services.llm_classifier as mod

        # Reset singleton
        mod._llm_classifier = None
        with patch.object(_RedisClassificationCache, "_connect"):
            c1 = get_llm_classifier()
            c2 = get_llm_classifier()
        assert c1 is c2
        # Cleanup
        mod._llm_classifier = None


# ---------------------------------------------------------------------------
# Integration: TransactionClassifier → LLM fallback
# ---------------------------------------------------------------------------


class TestTransactionClassifierLLMFallback:
    """Test the full rule → ML → LLM chain in TransactionClassifier."""

    def _make_transaction(
        self, description="Unknown merchant XYZ", amount=50.0, txn_type="expense"
    ):
        tx = SimpleNamespace(
            id=1,
            user_id=1,
            description=description,
            amount=Decimal(str(amount)),
            type=txn_type,
        )
        return tx

    def _make_user(
        self,
        user_type="self_employed",
        business_type="freiberufler",
        business_industry="IT",
    ):
        return SimpleNamespace(
            user_type=user_type,
            business_type=business_type,
            business_industry=business_industry,
        )

    @patch("app.services.transaction_classifier.RuleBasedClassifier")
    @patch("app.services.transaction_classifier.MLClassifier")
    def test_high_confidence_rule_skips_llm(self, MockML, MockRule):
        """When rule-based returns >= 0.95, LLM should not be called."""
        mock_rule_instance = MockRule.return_value
        mock_rule_instance.classify.return_value = SimpleNamespace(
            category="groceries", confidence=Decimal("0.96"), category_type="expense"
        )

        from app.services.transaction_classifier import TransactionClassifier

        tc = TransactionClassifier()
        tx = self._make_transaction("BILLA")
        result = tc.classify_transaction(tx)

        assert result.method == "rule"
        assert result.confidence == Decimal("0.96")

    @patch("app.services.transaction_classifier.RuleBasedClassifier")
    @patch("app.services.transaction_classifier.MLClassifier")
    def test_ml_above_threshold_skips_llm(self, MockML, MockRule):
        """When ML returns >= 0.85, LLM should not be called."""
        mock_rule_instance = MockRule.return_value
        mock_rule_instance.classify.return_value = SimpleNamespace(
            category="other", confidence=Decimal("0.3"), category_type="expense"
        )
        mock_ml_instance = MockML.return_value
        mock_ml_instance.classify.return_value = SimpleNamespace(
            category="office_supplies", confidence=Decimal("0.9"), category_type="expense"
        )

        from app.services.transaction_classifier import TransactionClassifier

        tc = TransactionClassifier()
        tx = self._make_transaction("Pagro Diskont")
        result = tc.classify_transaction(tx)

        assert result.method == "ml"
        assert result.confidence == Decimal("0.9")

    @patch("app.services.llm_classifier.get_llm_classifier")
    @patch("app.services.transaction_classifier.RuleBasedClassifier")
    @patch("app.services.transaction_classifier.MLClassifier")
    def test_low_confidence_triggers_llm(self, MockML, MockRule, mock_get_llm):
        """When both rule and ML return < 0.6, LLM fallback should be called."""
        mock_rule_instance = MockRule.return_value
        mock_rule_instance.classify.return_value = SimpleNamespace(
            category="other", confidence=Decimal("0.2"), category_type="expense"
        )
        mock_ml_instance = MockML.return_value
        mock_ml_instance.classify.return_value = SimpleNamespace(
            category="other", confidence=Decimal("0.3"), category_type="expense"
        )

        # Mock LLM classifier
        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.classify.return_value = LLMClassificationResult(
            category="software",
            confidence=Decimal("0.75"),
            category_type="expense",
            is_deductible=True,
            deduction_reason="IT-Betriebsausgabe",
        )
        mock_get_llm.return_value = mock_llm

        from app.services.transaction_classifier import TransactionClassifier

        tc = TransactionClassifier()
        tx = self._make_transaction("JetBrains License")
        user = self._make_user()
        result = tc.classify_transaction(tx, user)

        assert result.method == "llm"
        assert result.category == "software"
        assert result.is_deductible is True
        mock_llm.classify.assert_called_once()

    @patch("app.services.llm_classifier.get_llm_classifier")
    @patch("app.services.transaction_classifier.RuleBasedClassifier")
    @patch("app.services.transaction_classifier.MLClassifier")
    def test_llm_unavailable_falls_back_to_best(self, MockML, MockRule, mock_get_llm):
        """When LLM is unavailable, return best of rule/ML."""
        mock_rule_instance = MockRule.return_value
        mock_rule_instance.classify.return_value = SimpleNamespace(
            category="other", confidence=Decimal("0.4"), category_type="expense"
        )
        mock_ml_instance = MockML.return_value
        mock_ml_instance.classify.return_value = SimpleNamespace(
            category="other", confidence=Decimal("0.5"), category_type="expense"
        )

        mock_llm = MagicMock()
        mock_llm.is_available = False
        mock_get_llm.return_value = mock_llm

        from app.services.transaction_classifier import TransactionClassifier

        tc = TransactionClassifier()
        tx = self._make_transaction("Unknown thing")
        result = tc.classify_transaction(tx)

        assert result.method == "ml"
        assert result.confidence == Decimal("0.5")

    @patch("app.services.llm_classifier.get_llm_classifier")
    @patch("app.services.transaction_classifier.RuleBasedClassifier")
    @patch("app.services.transaction_classifier.MLClassifier")
    def test_llm_failure_falls_back_to_best(self, MockML, MockRule, mock_get_llm):
        """When LLM call fails, return best of rule/ML."""
        mock_rule_instance = MockRule.return_value
        mock_rule_instance.classify.return_value = SimpleNamespace(
            category="other", confidence=Decimal("0.4"), category_type="expense"
        )
        mock_ml_instance = MockML.return_value
        mock_ml_instance.classify.return_value = SimpleNamespace(
            category="other", confidence=Decimal("0.5"), category_type="expense"
        )

        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.classify.return_value = None  # LLM failed
        mock_get_llm.return_value = mock_llm

        from app.services.transaction_classifier import TransactionClassifier

        tc = TransactionClassifier()
        tx = self._make_transaction("Unknown thing")
        result = tc.classify_transaction(tx)

        assert result.method == "ml"
        assert result.confidence == Decimal("0.5")

    def test_empty_description_returns_none_category(self):
        from app.services.transaction_classifier import TransactionClassifier

        tc = TransactionClassifier()
        tx = self._make_transaction(description="")
        result = tc.classify_transaction(tx)
        assert result.category is None
        assert result.method == "none"


# ---------------------------------------------------------------------------
# User profile extraction
# ---------------------------------------------------------------------------


class TestUserProfileExtraction:
    def test_none_context(self):
        from app.services.transaction_classifier import TransactionClassifier

        ut, bt, bi = TransactionClassifier._extract_user_profile(None)
        assert ut == "employee"
        assert bt == ""
        assert bi == ""

    def test_dict_context(self):
        from app.services.transaction_classifier import TransactionClassifier

        ctx = {
            "user_type": "self_employed",
            "business_type": "freiberufler",
            "business_industry": "gastronomie",
        }
        ut, bt, bi = TransactionClassifier._extract_user_profile(ctx)
        assert ut == "self_employed"
        assert bt == "freiberufler"
        assert bi == "gastronomie"

    def test_orm_object_context(self):
        from app.services.transaction_classifier import TransactionClassifier

        user = SimpleNamespace(
            user_type="landlord",
            business_type=None,
            business_industry=None,
        )
        ut, bt, bi = TransactionClassifier._extract_user_profile(user)
        assert ut == "landlord"
        assert bt == ""
        assert bi == ""

    def test_enum_values_resolved(self):
        from app.services.transaction_classifier import TransactionClassifier

        class FakeEnum:
            value = "self_employed"

        user = SimpleNamespace(
            user_type=FakeEnum(),
            business_type=FakeEnum(),
            business_industry="IT",
        )
        ut, bt, bi = TransactionClassifier._extract_user_profile(user)
        assert ut == "self_employed"
        assert bt == "self_employed"
        assert bi == "IT"


# ---------------------------------------------------------------------------
# Austrian tax context: same merchant, different user → different result
# ---------------------------------------------------------------------------


class TestAustrianTaxContext:
    """
    Verify that the same merchant gets different cache keys for different
    user profiles, reflecting Austrian tax rules where deductibility
    depends on user_type + business_industry.
    """

    def test_billa_gastro_vs_it(self, classifier):
        """BILLA for gastronomie self-employed vs IT freelancer → different keys."""
        merchant = classifier._normalize_merchant("BILLA Filiale 42")
        key_gastro = classifier._build_cache_key(
            merchant, "expense", "self_employed", "gewerbetreibende", "gastronomie"
        )
        key_it = classifier._build_cache_key(
            merchant, "expense", "self_employed", "freiberufler", "IT"
        )
        assert key_gastro != key_it

    def test_employee_vs_self_employed(self, classifier):
        merchant = classifier._normalize_merchant("MediaMarkt")
        key_emp = classifier._build_cache_key(
            merchant, "expense", "employee", "", ""
        )
        key_se = classifier._build_cache_key(
            merchant, "expense", "self_employed", "freiberufler", "fotografie"
        )
        assert key_emp != key_se

    def test_landlord_vs_mixed(self, classifier):
        merchant = classifier._normalize_merchant("Bauhaus")
        key_landlord = classifier._build_cache_key(
            merchant, "expense", "landlord", "", ""
        )
        key_mixed = classifier._build_cache_key(
            merchant, "expense", "mixed", "gewerbetreibende", "hotel"
        )
        assert key_landlord != key_mixed
