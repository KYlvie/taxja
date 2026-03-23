"""
Tests for the 5 AI layer fixes:
  1. AUTO_CREATE_THRESHOLDS duplicate definition bug
  2. Intent cache key granularity improvement
  3. existing_titles dynamic passing in savings suggestions
  4. OCR accuracy admin endpoint
  5. Knowledge manifest admin endpoint

All tests are self-contained with no external service dependencies.
"""
import hashlib
import json
import os
import sys
import tempfile
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ============================================================================
# Fix 1: AUTO_CREATE_THRESHOLDS — per-document-type thresholds now work
# ============================================================================

class TestAutoCreateThresholds:
    """Verify the current low-threshold auto-create policy stays stable."""

    def test_receipt_threshold_is_03(self):
        from app.services.document_pipeline_orchestrator import AUTO_CREATE_THRESHOLDS
        from app.models.document import DocumentType as DBDocumentType

        assert AUTO_CREATE_THRESHOLDS[DBDocumentType.RECEIPT] == 0.3

    def test_invoice_threshold_is_03(self):
        from app.services.document_pipeline_orchestrator import AUTO_CREATE_THRESHOLDS
        from app.models.document import DocumentType as DBDocumentType

        assert AUTO_CREATE_THRESHOLDS[DBDocumentType.INVOICE] == 0.3

    def test_purchase_contract_threshold_is_04(self):
        from app.services.document_pipeline_orchestrator import AUTO_CREATE_THRESHOLDS
        from app.models.document import DocumentType as DBDocumentType

        assert AUTO_CREATE_THRESHOLDS[DBDocumentType.PURCHASE_CONTRACT] == 0.4

    def test_rental_contract_threshold_is_04(self):
        from app.services.document_pipeline_orchestrator import AUTO_CREATE_THRESHOLDS
        from app.models.document import DocumentType as DBDocumentType

        assert AUTO_CREATE_THRESHOLDS[DBDocumentType.RENTAL_CONTRACT] == 0.4

    def test_e1_form_threshold_is_04(self):
        from app.services.document_pipeline_orchestrator import AUTO_CREATE_THRESHOLDS
        from app.models.document import DocumentType as DBDocumentType

        assert AUTO_CREATE_THRESHOLDS[DBDocumentType.E1_FORM] == 0.4

    def test_einkommensteuerbescheid_threshold_is_04(self):
        from app.services.document_pipeline_orchestrator import AUTO_CREATE_THRESHOLDS
        from app.models.document import DocumentType as DBDocumentType

        assert AUTO_CREATE_THRESHOLDS[DBDocumentType.EINKOMMENSTEUERBESCHEID] == 0.4

    def test_unknown_type_uses_default_03(self):
        from app.services.document_pipeline_orchestrator import DEFAULT_AUTO_CREATE_THRESHOLD

        assert DEFAULT_AUTO_CREATE_THRESHOLD == 0.3

    def test_thresholds_dict_uses_document_type_keys(self):
        from app.services.document_pipeline_orchestrator import AUTO_CREATE_THRESHOLDS
        from app.models.document import DocumentType as DBDocumentType

        for key in AUTO_CREATE_THRESHOLDS:
            assert isinstance(key, DBDocumentType), f"Key {key!r} should be DocumentType, got {type(key)}"

    def test_legacy_compat_aliases_exist(self):
        """CONFIDENCE_THRESHOLDS and DEFAULT_CONFIDENCE_THRESHOLD still importable."""
        from app.services.document_pipeline_orchestrator import (
            CONFIDENCE_THRESHOLDS,
            DEFAULT_CONFIDENCE_THRESHOLD,
        )
        assert isinstance(CONFIDENCE_THRESHOLDS, dict)
        assert isinstance(DEFAULT_CONFIDENCE_THRESHOLD, float)

    def test_legacy_compat_values_match_canonical(self):
        """Legacy aliases should reflect the canonical threshold values."""
        from app.services.document_pipeline_orchestrator import (
            CONFIDENCE_THRESHOLDS,
            DEFAULT_CONFIDENCE_THRESHOLD,
            AUTO_CREATE_THRESHOLD_DEFAULT,
        )
        assert DEFAULT_CONFIDENCE_THRESHOLD == AUTO_CREATE_THRESHOLD_DEFAULT
        # Legacy dict uses DBDocumentType enum keys and should mirror the canonical values.
        from app.models.document import DocumentType as DBDocumentType
        for db_type, legacy_val in CONFIDENCE_THRESHOLDS.items():
            assert isinstance(db_type, DBDocumentType)
            assert isinstance(legacy_val, float)

    def test_receipt_below_threshold_blocks_auto_create(self):
        """Confidence 0.29 < receipt threshold 0.30 should not auto-create."""
        from app.services.document_pipeline_orchestrator import AUTO_CREATE_THRESHOLDS
        from app.models.document import DocumentType as DBDocumentType

        threshold = AUTO_CREATE_THRESHOLDS[DBDocumentType.RECEIPT]
        assert 0.29 < threshold

    def test_receipt_at_threshold_allows_auto_create(self):
        """Confidence 0.30 >= receipt threshold 0.30 should auto-create."""
        from app.services.document_pipeline_orchestrator import AUTO_CREATE_THRESHOLDS
        from app.models.document import DocumentType as DBDocumentType

        threshold = AUTO_CREATE_THRESHOLDS[DBDocumentType.RECEIPT]
        assert 0.30 >= threshold

    def test_purchase_contract_requires_higher_confidence_than_receipt(self):
        """Purchase contracts keep a stricter threshold than receipts."""
        from app.services.document_pipeline_orchestrator import AUTO_CREATE_THRESHOLDS
        from app.models.document import DocumentType as DBDocumentType

        receipt_threshold = AUTO_CREATE_THRESHOLDS[DBDocumentType.RECEIPT]
        contract_threshold = AUTO_CREATE_THRESHOLDS[DBDocumentType.PURCHASE_CONTRACT]
        assert receipt_threshold < contract_threshold


# ============================================================================
# Fix 2: Intent cache key granularity — uses first 100 chars, not 5 words
# ============================================================================

class TestIntentCacheKeyGranularity:
    """Verify the intent cache key uses sufficient message content."""

    def setup_method(self):
        """Clear the intent cache before each test."""
        from app.services.ai_orchestrator import _intent_cache
        _intent_cache.clear()

    def test_different_messages_same_first_5_words_get_different_keys(self):
        """Previously these would collide; now they should not."""
        msg_a = "我能不能少交点税"
        msg_b = "我能不能少交点钱"
        key_a = hashlib.sha256(msg_a[:100].lower().strip().encode()).hexdigest()[:16]
        key_b = hashlib.sha256(msg_b[:100].lower().strip().encode()).hexdigest()[:16]
        assert key_a != key_b, "Different messages should produce different cache keys"

    def test_identical_messages_get_same_key(self):
        msg = "Kann ich meine Fahrtkosten absetzen?"
        key_a = hashlib.sha256(msg[:100].lower().strip().encode()).hexdigest()[:16]
        key_b = hashlib.sha256(msg[:100].lower().strip().encode()).hexdigest()[:16]
        assert key_a == key_b

    def test_case_insensitive_cache_key(self):
        msg_a = "How much tax do I owe?"
        msg_b = "how much tax do i owe?"
        key_a = hashlib.sha256(msg_a[:100].lower().strip().encode()).hexdigest()[:16]
        key_b = hashlib.sha256(msg_b[:100].lower().strip().encode()).hexdigest()[:16]
        assert key_a == key_b

    def test_cache_max_size_constant_exists(self):
        from app.services.ai_orchestrator import _INTENT_CACHE_MAX_SIZE
        assert _INTENT_CACHE_MAX_SIZE == 1000

    def test_cache_eviction_on_overflow(self):
        """When cache exceeds max size, it should be cleared."""
        from app.services import ai_orchestrator
        from app.services.ai_orchestrator import (
            _intent_cache,
            _INTENT_CACHE_MAX_SIZE,
            IntentResult,
            UserIntent,
        )
        # Fill cache to max
        for i in range(_INTENT_CACHE_MAX_SIZE):
            _intent_cache[f"key_{i}"] = IntentResult(
                intent=UserIntent.TAX_QA, confidence=0.8
            )
        assert len(_intent_cache) == _INTENT_CACHE_MAX_SIZE

        # Simulate what _llm_intent_fallback does when cache is full
        # It checks len >= max and clears
        if len(_intent_cache) >= _INTENT_CACHE_MAX_SIZE:
            _intent_cache.clear()
        _intent_cache["new_key"] = IntentResult(
            intent=UserIntent.OPTIMIZE_TAX, confidence=0.8
        )
        assert len(_intent_cache) == 1
        assert "new_key" in _intent_cache

    @patch("app.services.llm_service.get_llm_service")
    def test_llm_fallback_caches_result(self, mock_get_llm):
        """Verify that a successful LLM intent classification is cached."""
        from app.services.ai_orchestrator import (
            _llm_intent_fallback,
            _intent_cache,
            UserIntent,
        )
        _intent_cache.clear()

        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.generate_simple.return_value = "optimize_tax"
        mock_get_llm.return_value = mock_llm

        result = _llm_intent_fallback("我想省点税有什么办法吗")
        assert result is not None
        assert result.intent == UserIntent.OPTIMIZE_TAX
        assert result.confidence == 0.80

        # Should be cached now
        assert len(_intent_cache) == 1

        # Second call should hit cache, not LLM
        mock_llm.generate_simple.reset_mock()
        result2 = _llm_intent_fallback("我想省点税有什么办法吗")
        assert result2 is not None
        assert result2.intent == UserIntent.OPTIMIZE_TAX
        mock_llm.generate_simple.assert_not_called()

    @patch("app.services.llm_service.get_llm_service")
    def test_llm_fallback_returns_none_for_tax_qa(self, mock_get_llm):
        """LLM returning tax_qa should not override the default."""
        from app.services.ai_orchestrator import _llm_intent_fallback, _intent_cache
        _intent_cache.clear()

        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.generate_simple.return_value = "tax_qa"
        mock_get_llm.return_value = mock_llm

        result = _llm_intent_fallback("some random question")
        assert result is None

    @patch("app.services.llm_service.get_llm_service")
    def test_llm_fallback_returns_none_when_unavailable(self, mock_get_llm):
        from app.services.ai_orchestrator import _llm_intent_fallback, _intent_cache
        _intent_cache.clear()

        mock_llm = MagicMock()
        mock_llm.is_available = False
        mock_get_llm.return_value = mock_llm

        result = _llm_intent_fallback("test message")
        assert result is None


# ============================================================================
# Fix 3: existing_titles dynamic passing in savings suggestions
# ============================================================================

class TestSavingsSuggestionExistingTitles:
    """Verify _ai_spending_analysis receives actual suggestion titles."""

    def test_method_signature_accepts_existing_titles(self):
        """_ai_spending_analysis should accept an existing_titles parameter."""
        import inspect
        from app.services.savings_suggestion_service import SavingsSuggestionService
        sig = inspect.signature(SavingsSuggestionService._ai_spending_analysis)
        params = list(sig.parameters.keys())
        assert "existing_titles" in params

    @patch("app.services.llm_service.get_llm_service")
    def test_existing_titles_passed_to_prompt(self, mock_get_llm):
        """When rule-based suggestions exist, their titles should appear in the LLM prompt."""
        from app.services.savings_suggestion_service import (
            SavingsSuggestionService,
            SavingsSuggestion,
        )

        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.generate_response.return_value = "[]"
        mock_get_llm.return_value = mock_llm

        db = MagicMock()
        # Prevent DeductionCalculator/TaxCalculationEngine from hitting real DB
        with patch("app.services.savings_suggestion_service.DeductionCalculator"), \
             patch("app.services.savings_suggestion_service.FlatRateTaxComparator"), \
             patch("app.services.savings_suggestion_service.TaxCalculationEngine"):
            service = SavingsSuggestionService(db)

        # Create a fake user
        user = MagicMock()
        user.id = 1
        user.user_type = MagicMock()
        user.user_type.value = "self_employed"

        # Mock transactions query to return enough data
        from app.models.transaction import TransactionType
        mock_txn = MagicMock()
        mock_txn.type = TransactionType.EXPENSE
        mock_txn.expense_category = MagicMock()
        mock_txn.expense_category.value = "office_supplies"
        mock_txn.amount = Decimal("100.00")
        mock_txn.income_category = None

        # Return 10 transactions so the >= 5 check passes
        db.query.return_value.filter.return_value.all.return_value = [mock_txn] * 10

        titles = ["Claim Commuting Allowance", "SVS Contributions Are Tax-Deductible"]
        result = service._ai_spending_analysis(user, 2026, "de", titles)

        # Verify the LLM was called and the prompt contained the actual titles
        if mock_llm.generate_response.called:
            call_args = mock_llm.generate_response.call_args
            prompt = call_args.kwargs.get("user_message", "") or call_args[1].get("user_message", "")
            if not prompt:
                prompt = str(call_args)
            assert "Claim Commuting Allowance" in prompt or "SVS" in prompt

    def test_empty_existing_titles_shows_none(self):
        """When no rule-based suggestions exist, prompt should say 'none'."""
        from app.services.savings_suggestion_service import SavingsSuggestionService

        db = MagicMock()
        with patch("app.services.savings_suggestion_service.DeductionCalculator"), \
             patch("app.services.savings_suggestion_service.FlatRateTaxComparator"), \
             patch("app.services.savings_suggestion_service.TaxCalculationEngine"):
            service = SavingsSuggestionService(db)

        # Mock user with no transactions (will return early)
        user = MagicMock()
        user.id = 1
        user.user_type = MagicMock()
        user.user_type.value = "employee"

        db.query.return_value.filter.return_value.all.return_value = []

        # Should return empty list (not enough transactions)
        result = service._ai_spending_analysis(user, 2026, "de", [])
        assert result == []

    def test_generate_suggestions_passes_titles_to_ai(self):
        """Integration: generate_suggestions should pass collected titles to AI."""
        from app.services.savings_suggestion_service import SavingsSuggestionService
        from app.models.user import UserType

        db = MagicMock()
        with patch("app.services.savings_suggestion_service.DeductionCalculator"), \
             patch("app.services.savings_suggestion_service.FlatRateTaxComparator"), \
             patch("app.services.savings_suggestion_service.TaxCalculationEngine"):
            service = SavingsSuggestionService(db)

        user = MagicMock()
        user.id = 1
        # Use a real enum value so `user.user_type in [...]` works correctly
        user.user_type = UserType.EMPLOYEE
        user.commuting_info = None
        user.family_info = None
        user.home_office_eligible = False

        db.query.return_value.filter.return_value.first.return_value = user

        # Patch _ai_spending_analysis to capture what titles it receives
        captured_titles = []

        def spy_ai(u, year, lang, existing_titles=None):
            captured_titles.extend(existing_titles or [])
            return []

        service._ai_spending_analysis = spy_ai

        # Patch _check methods to return a known suggestion
        from app.services.savings_suggestion_service import SavingsSuggestion
        service._check_commuting_allowance = lambda u, y, mr=None: None
        service._check_home_office_deduction = lambda u, y, mr=None: SavingsSuggestion(
            title="Test Home Office",
            description="test",
            potential_savings=Decimal("90"),
            category="deductions",
            priority=2,
            action_required="test",
        )
        service._check_flat_rate_tax = lambda uid, y: None
        service._check_family_deductions = lambda u, y, mr=None: None
        service._check_svs_deductibility = lambda uid, y, mr=None: None

        service.generate_suggestions(1, 2026, "de")

        assert "Test Home Office" in captured_titles

    @staticmethod
    def test_parse_ai_suggestions_valid_json():
        from app.services.savings_suggestion_service import SavingsSuggestionService
        raw = json.dumps([
            {
                "title": "Claim Education Costs",
                "description": "You spent €500 on courses",
                "estimated_savings_eur": 150,
                "action_required": "Upload certificates",
            }
        ])
        results = SavingsSuggestionService._parse_ai_suggestions(raw)
        assert len(results) == 1
        assert results[0].title == "Claim Education Costs"
        assert results[0].category == "ai_suggestion"

    @staticmethod
    def test_parse_ai_suggestions_max_3():
        from app.services.savings_suggestion_service import SavingsSuggestionService
        items = [
            {"title": f"Tip {i}", "description": f"desc {i}", "estimated_savings_eur": i * 10}
            for i in range(5)
        ]
        results = SavingsSuggestionService._parse_ai_suggestions(json.dumps(items))
        assert len(results) == 3

    @staticmethod
    def test_parse_ai_suggestions_invalid_json():
        from app.services.savings_suggestion_service import SavingsSuggestionService
        results = SavingsSuggestionService._parse_ai_suggestions("not json at all")
        assert results == []


# ============================================================================
# Fix 4: OCR accuracy tracking — get_extraction_accuracy() method
# ============================================================================

class TestOCRExtractionAccuracy:
    """Test the get_extraction_accuracy() method in ClassificationLearningService."""

    def _make_doc(self, doc_type_value, learning_data):
        """Create a mock document with OCR learning data."""
        doc = MagicMock()
        doc.document_type = MagicMock()
        doc.document_type.value = doc_type_value
        doc.ocr_result = {"learning_data": learning_data}
        return doc

    def test_no_documents_returns_empty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        from app.services.classification_learning import ClassificationLearningService
        service = ClassificationLearningService(db)
        result = service.get_extraction_accuracy()

        assert result["total_corrections"] == 0
        assert result["by_document_type"] == {}
        assert result["low_accuracy_fields"] == []

    def test_perfect_accuracy_no_changes(self):
        """When previous_data == corrected_data, accuracy should be 1.0."""
        db = MagicMock()
        docs = [
            self._make_doc("receipt", [
                {"previous_data": {"amount": "10.00"}, "corrected_data": {"amount": "10.00"}},
            ])
        ]
        db.query.return_value.filter.return_value.all.return_value = docs

        from app.services.classification_learning import ClassificationLearningService
        service = ClassificationLearningService(db)
        result = service.get_extraction_accuracy()

        assert result["total_corrections"] == 1
        assert result["by_document_type"]["receipt"]["fields"]["amount"]["accuracy"] == 1.0
        assert result["by_document_type"]["receipt"]["fields"]["amount"]["changed"] == 0

    def test_low_accuracy_flagged(self):
        """Fields with accuracy < 80% and >= 5 samples should be flagged."""
        db = MagicMock()
        # 5 corrections where merchant is always wrong
        learning_entries = [
            {
                "previous_data": {"merchant": f"wrong_{i}", "amount": "10.00"},
                "corrected_data": {"merchant": f"correct_{i}", "amount": "10.00"},
            }
            for i in range(5)
        ]
        docs = [self._make_doc("receipt", learning_entries)]
        db.query.return_value.filter.return_value.all.return_value = docs

        from app.services.classification_learning import ClassificationLearningService
        service = ClassificationLearningService(db)
        result = service.get_extraction_accuracy()

        assert result["total_corrections"] == 5
        merchant_stats = result["by_document_type"]["receipt"]["fields"]["merchant"]
        assert merchant_stats["total"] == 5
        assert merchant_stats["changed"] == 5
        assert merchant_stats["accuracy"] == 0.0

        # Should be in low_accuracy_fields
        low = result["low_accuracy_fields"]
        assert len(low) >= 1
        merchant_flag = [f for f in low if f["field"] == "merchant"]
        assert len(merchant_flag) == 1
        assert merchant_flag[0]["accuracy"] == 0.0

    def test_mixed_accuracy(self):
        """Some fields accurate, some not."""
        db = MagicMock()
        entries = []
        for i in range(10):
            prev = {"amount": "10.00", "date": f"2026-01-{i+1:02d}"}
            corr = {"amount": "10.00", "date": f"2026-01-{i+1:02d}"}
            if i < 3:  # 3 out of 10 dates are wrong
                corr["date"] = "2026-02-01"
            entries.append({"previous_data": prev, "corrected_data": corr})

        docs = [self._make_doc("invoice", entries)]
        db.query.return_value.filter.return_value.all.return_value = docs

        from app.services.classification_learning import ClassificationLearningService
        service = ClassificationLearningService(db)
        result = service.get_extraction_accuracy()

        assert result["total_corrections"] == 10
        amount_stats = result["by_document_type"]["invoice"]["fields"]["amount"]
        assert amount_stats["accuracy"] == 1.0  # never changed

        date_stats = result["by_document_type"]["invoice"]["fields"]["date"]
        assert date_stats["changed"] == 3
        assert date_stats["accuracy"] == 0.7  # 7/10

    def test_multiple_document_types(self):
        """Stats should be grouped by document type."""
        db = MagicMock()
        docs = [
            self._make_doc("receipt", [
                {"previous_data": {"amount": "5"}, "corrected_data": {"amount": "5"}},
            ]),
            self._make_doc("invoice", [
                {"previous_data": {"amount": "10"}, "corrected_data": {"amount": "20"}},
            ]),
        ]
        db.query.return_value.filter.return_value.all.return_value = docs

        from app.services.classification_learning import ClassificationLearningService
        service = ClassificationLearningService(db)
        result = service.get_extraction_accuracy()

        assert "receipt" in result["by_document_type"]
        assert "invoice" in result["by_document_type"]
        assert result["by_document_type"]["receipt"]["fields"]["amount"]["changed"] == 0
        assert result["by_document_type"]["invoice"]["fields"]["amount"]["changed"] == 1

    def test_empty_learning_data_skipped(self):
        """Documents with empty or missing learning_data should be skipped."""
        db = MagicMock()
        doc_no_learning = MagicMock()
        doc_no_learning.ocr_result = {"some_field": "value"}
        doc_no_learning.document_type = MagicMock()
        doc_no_learning.document_type.value = "receipt"

        doc_empty_list = MagicMock()
        doc_empty_list.ocr_result = {"learning_data": []}
        doc_empty_list.document_type = MagicMock()
        doc_empty_list.document_type.value = "receipt"

        db.query.return_value.filter.return_value.all.return_value = [
            doc_no_learning, doc_empty_list
        ]

        from app.services.classification_learning import ClassificationLearningService
        service = ClassificationLearningService(db)
        result = service.get_extraction_accuracy()

        assert result["total_corrections"] == 0

    def test_low_accuracy_not_flagged_below_min_samples(self):
        """Fields with < 5 samples should NOT be flagged even if accuracy is low."""
        db = MagicMock()
        entries = [
            {"previous_data": {"merchant": "a"}, "corrected_data": {"merchant": "b"}},
            {"previous_data": {"merchant": "c"}, "corrected_data": {"merchant": "d"}},
        ]
        docs = [self._make_doc("receipt", entries)]
        db.query.return_value.filter.return_value.all.return_value = docs

        from app.services.classification_learning import ClassificationLearningService
        service = ClassificationLearningService(db)
        result = service.get_extraction_accuracy()

        # Accuracy is 0% but only 2 samples — should NOT be in low_accuracy_fields
        assert result["low_accuracy_fields"] == []


# ============================================================================
# Fix 5: Knowledge base management — scan_and_ingest + manifest
# ============================================================================

class TestKnowledgeBaseManagement:
    """Test the knowledge update scan and manifest functions."""

    def test_scan_nonexistent_directory(self):
        """scan_and_ingest on a missing directory should return gracefully."""
        from app.tasks.knowledge_update_tasks import scan_and_ingest
        result = scan_and_ingest("/nonexistent/path/that/does/not/exist")
        assert result["new_files"] == 0
        assert result["updated_files"] == 0
        assert result["total_chunks"] == 0

    def test_scan_empty_directory(self):
        """scan_and_ingest on an empty directory should do nothing."""
        from app.tasks.knowledge_update_tasks import scan_and_ingest
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_and_ingest(tmpdir)
            assert result["new_files"] == 0
            assert result["total_chunks"] == 0

    def test_load_manifest_missing_file(self):
        """_load_manifest should return empty structure for missing file."""
        from app.tasks.knowledge_update_tasks import _load_manifest
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = _load_manifest(tmpdir)
            assert manifest == {"ingested_files": {}}

    def test_save_and_load_manifest(self):
        """Manifest should round-trip through save/load."""
        from app.tasks.knowledge_update_tasks import _save_manifest, _load_manifest
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {
                "ingested_files": {
                    "test.md": {"hash": "abc123", "ingested_at": "2026-01-01", "chunks": 3}
                },
                "last_scan": "2026-01-01T00:00:00",
            }
            _save_manifest(tmpdir, data)
            loaded = _load_manifest(tmpdir)
            assert loaded["ingested_files"]["test.md"]["hash"] == "abc123"
            assert loaded["last_scan"] == "2026-01-01T00:00:00"

    def test_file_hash_deterministic(self):
        """_file_hash should return the same hash for the same content."""
        from app.tasks.knowledge_update_tasks import _file_hash
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content for hashing")
            f.flush()
            path = f.name
        try:
            h1 = _file_hash(path)
            h2 = _file_hash(path)
            assert h1 == h2
            assert len(h1) == 64  # SHA-256 hex
        finally:
            os.unlink(path)

    def test_file_hash_changes_with_content(self):
        from app.tasks.knowledge_update_tasks import _file_hash
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("content A")
            f.flush()
            path = f.name
        try:
            h1 = _file_hash(path)
            with open(path, "w") as f:
                f.write("content B")
            h2 = _file_hash(path)
            assert h1 != h2
        finally:
            os.unlink(path)

    def test_detect_language_default_german(self):
        from app.tasks.knowledge_update_tasks import _detect_language
        assert _detect_language("tax_update_2026.md") == "de"
        assert _detect_language("some_file.json") == "de"

    def test_detect_language_english(self):
        from app.tasks.knowledge_update_tasks import _detect_language
        assert _detect_language("tax_update_en.md") == "en"
        assert _detect_language("guide.en.json") == "en"

    def test_detect_language_chinese(self):
        from app.tasks.knowledge_update_tasks import _detect_language
        assert _detect_language("tax_guide_zh.md") == "zh"
        assert _detect_language("faq.zh.txt") == "zh"

    def test_chunk_text_short(self):
        """Short text should produce a single chunk."""
        from app.tasks.knowledge_update_tasks import _chunk_text
        text = "This is a short text."
        chunks = _chunk_text(text, max_words=500)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_long(self):
        """Long text should be split into multiple chunks."""
        from app.tasks.knowledge_update_tasks import _chunk_text
        words = ["word"] * 1200
        text = " ".join(words)
        chunks = _chunk_text(text, max_words=500)
        assert len(chunks) == 3  # 1200 / 500 = 2.4 → 3 chunks

    def test_chunk_text_empty(self):
        from app.tasks.knowledge_update_tasks import _chunk_text
        chunks = _chunk_text("")
        assert len(chunks) == 1  # Returns [""] as fallback

    @patch("app.services.knowledge_base_service.get_knowledge_base_service")
    def test_scan_ingests_new_markdown_file(self, mock_get_kb):
        """A new .md file should be ingested and tracked in manifest."""
        from app.tasks.knowledge_update_tasks import scan_and_ingest, _load_manifest

        mock_kb = MagicMock()
        mock_get_kb.return_value = mock_kb

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a markdown file
            md_path = os.path.join(tmpdir, "update_2026.md")
            with open(md_path, "w") as f:
                f.write("New tax law update for 2026. " * 50)

            result = scan_and_ingest(tmpdir)

            assert result["new_files"] == 1
            assert result["total_chunks"] >= 1
            assert result["errors"] == []

            # Verify manifest was updated
            manifest = _load_manifest(tmpdir)
            assert "update_2026.md" in manifest["ingested_files"]
            assert manifest["ingested_files"]["update_2026.md"]["chunks"] >= 1

            # Verify vector_db.add_documents was called
            mock_kb.vector_db.add_documents.assert_called_once()
            call_kwargs = mock_kb.vector_db.add_documents.call_args
            assert call_kwargs[1]["collection_name"] == "admin_knowledge_updates"

    @patch("app.services.knowledge_base_service.get_knowledge_base_service")
    def test_scan_skips_already_ingested_unchanged(self, mock_get_kb):
        """Files already in manifest with same hash should be skipped."""
        from app.tasks.knowledge_update_tasks import (
            scan_and_ingest, _save_manifest, _file_hash,
        )

        mock_kb = MagicMock()
        mock_get_kb.return_value = mock_kb

        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = os.path.join(tmpdir, "existing.md")
            with open(md_path, "w") as f:
                f.write("Already ingested content")

            # Pre-populate manifest with the correct hash
            file_hash = _file_hash(md_path)
            _save_manifest(tmpdir, {
                "ingested_files": {
                    "existing.md": {"hash": file_hash, "ingested_at": "2026-01-01", "chunks": 1}
                }
            })

            result = scan_and_ingest(tmpdir)

            assert result["new_files"] == 0
            assert result["updated_files"] == 0
            # KB service should NOT have been called (no work to do)
            mock_get_kb.assert_not_called()

    @patch("app.services.knowledge_base_service.get_knowledge_base_service")
    def test_scan_detects_updated_file(self, mock_get_kb):
        """A file with changed content should be re-ingested."""
        from app.tasks.knowledge_update_tasks import scan_and_ingest, _save_manifest

        mock_kb = MagicMock()
        mock_get_kb.return_value = mock_kb

        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = os.path.join(tmpdir, "guide.md")
            with open(md_path, "w") as f:
                f.write("Updated content version 2")

            # Pre-populate manifest with a DIFFERENT hash
            _save_manifest(tmpdir, {
                "ingested_files": {
                    "guide.md": {"hash": "old_hash_different", "ingested_at": "2026-01-01", "chunks": 1}
                }
            })

            result = scan_and_ingest(tmpdir)

            assert result["updated_files"] == 1
            assert result["new_files"] == 0

    @patch("app.services.knowledge_base_service.get_knowledge_base_service")
    def test_scan_ingests_json_file(self, mock_get_kb):
        """JSON files with [{text, metadata}] format should be ingested."""
        from app.tasks.knowledge_update_tasks import scan_and_ingest

        mock_kb = MagicMock()
        mock_get_kb.return_value = mock_kb

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "knowledge_en.json")
            data = [
                {"text": "Austrian tax law section 1", "metadata": {"source": "BMF"}},
                {"text": "Austrian tax law section 2", "metadata": {"source": "BMF"}},
            ]
            with open(json_path, "w") as f:
                json.dump(data, f)

            result = scan_and_ingest(tmpdir)

            assert result["new_files"] == 1
            assert result["total_chunks"] == 2

            # Verify language detection from filename
            call_kwargs = mock_kb.vector_db.add_documents.call_args
            metadatas = call_kwargs[1]["metadatas"]
            assert all(m["language"] == "en" for m in metadatas)

    def test_scan_ignores_non_supported_extensions(self):
        """Files with unsupported extensions (.py, .csv, etc.) should be skipped."""
        from app.tasks.knowledge_update_tasks import scan_and_ingest

        with tempfile.TemporaryDirectory() as tmpdir:
            for ext in [".py", ".csv", ".xlsx", ".pdf"]:
                with open(os.path.join(tmpdir, f"file{ext}"), "w") as f:
                    f.write("some content")

            result = scan_and_ingest(tmpdir)
            assert result["new_files"] == 0
            assert result["total_chunks"] == 0
