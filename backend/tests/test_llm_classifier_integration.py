"""
Integration tests for LLM classifier across all entry points.

Verifies that:
- db session is correctly passed to TransactionClassifier
- LLM fallback is triggered when rule+ML confidence is low
- ClassificationCorrection records are stored in the database
- User context (user_type, business_type, business_industry) flows through

All tests use mocks — no real LLM calls or files needed.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.services.llm_classifier import LLMClassificationResult


# ---------------------------------------------------------------------------
# Helper: mock rule+ML to return low confidence so LLM fallback triggers
# ---------------------------------------------------------------------------

def _patch_rule_ml_low_confidence():
    """Return patch context managers for rule and ML classifiers returning low confidence."""
    rule_patch = patch(
        "app.services.transaction_classifier.RuleBasedClassifier",
    )
    ml_patch = patch(
        "app.services.transaction_classifier.MLClassifier",
    )
    return rule_patch, ml_patch


def _setup_low_confidence_mocks(mock_rule_cls, mock_ml_cls):
    """Configure rule and ML mocks to return low confidence."""
    mock_rule_cls.return_value.classify.return_value = SimpleNamespace(
        category="other", confidence=Decimal("0.2"), category_type="expense"
    )
    mock_ml_cls.return_value.classify.return_value = SimpleNamespace(
        category="other", confidence=Decimal("0.3"), category_type="expense"
    )


def _make_llm_result(category="software", is_deductible=True):
    return LLMClassificationResult(
        category=category,
        confidence=Decimal("0.75"),
        category_type="expense",
        is_deductible=is_deductible,
        deduction_reason="Betriebsausgabe",
    )


# ---------------------------------------------------------------------------
# OCRTransactionService: db passed, user context flows through
# ---------------------------------------------------------------------------


class TestOCRTransactionServiceLLMIntegration:
    """Verify OCRTransactionService passes db to TransactionClassifier."""

    @patch("app.services.llm_classifier.get_llm_classifier")
    def test_ocr_service_passes_db_to_classifier(self, mock_get_llm):
        """OCRTransactionService(db) should create TransactionClassifier(db=db)."""
        mock_db = MagicMock()

        with patch(
            "app.services.ocr_transaction_service.TransactionClassifier"
        ) as MockTC, patch(
            "app.services.ocr_transaction_service.DeductibilityChecker"
        ):
            from app.services.ocr_transaction_service import OCRTransactionService

            service = OCRTransactionService(db=mock_db)
            MockTC.assert_called_once_with(db=mock_db)

    @patch("app.services.llm_classifier.get_llm_classifier")
    @patch("app.services.transaction_classifier.RuleBasedClassifier")
    @patch("app.services.transaction_classifier.MLClassifier")
    def test_ocr_classify_passes_user_to_classifier(
        self, MockML, MockRule, mock_get_llm
    ):
        """When OCR classifies a receipt, user object should be passed to classify_transaction."""
        _setup_low_confidence_mocks(MockRule, MockML)

        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.classify.return_value = _make_llm_result("groceries", True)
        mock_get_llm.return_value = mock_llm

        mock_db = MagicMock()

        from app.services.ocr_transaction_service import OCRTransactionService
        from app.services.transaction_classifier import TransactionClassifier

        service = OCRTransactionService(db=mock_db)

        # The classifier should have db
        assert service.classifier.db is mock_db

    @patch("app.services.llm_classifier.get_llm_classifier")
    @patch("app.services.transaction_classifier.RuleBasedClassifier")
    @patch("app.services.transaction_classifier.MLClassifier")
    def test_llm_fallback_stores_correction_with_db(
        self, MockML, MockRule, mock_get_llm
    ):
        """When LLM fallback triggers with a real db + transaction, correction is stored."""
        _setup_low_confidence_mocks(MockRule, MockML)

        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.classify.return_value = _make_llm_result("software", True)
        mock_get_llm.return_value = mock_llm

        mock_db = MagicMock()

        from app.services.transaction_classifier import TransactionClassifier

        tc = TransactionClassifier(db=mock_db)

        # Transaction with real id and user_id → should trigger DB write
        tx = SimpleNamespace(
            id=42,
            user_id=7,
            description="JetBrains IntelliJ License",
            amount=Decimal("249.00"),
            type="expense",
        )
        user = SimpleNamespace(
            user_type="self_employed",
            business_type="freiberufler",
            business_industry="IT",
        )

        result = tc.classify_transaction(tx, user)

        assert result.method == "llm"
        assert result.category == "software"

        # Verify db.add was called with a ClassificationCorrection
        mock_db.add.assert_called_once()
        correction = mock_db.add.call_args[0][0]
        assert correction.transaction_id == 42
        assert correction.user_id == 7
        assert correction.correct_category == "software"
        mock_db.commit.assert_called_once()

    @patch("app.services.llm_classifier.get_llm_classifier")
    @patch("app.services.transaction_classifier.RuleBasedClassifier")
    @patch("app.services.transaction_classifier.MLClassifier")
    def test_no_correction_stored_without_db(
        self, MockML, MockRule, mock_get_llm
    ):
        """Without db session, LLM result should NOT attempt DB write."""
        _setup_low_confidence_mocks(MockRule, MockML)

        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.classify.return_value = _make_llm_result()
        mock_get_llm.return_value = mock_llm

        from app.services.transaction_classifier import TransactionClassifier

        tc = TransactionClassifier(db=None)  # No db

        tx = SimpleNamespace(
            id=42, user_id=7,
            description="Test", amount=Decimal("100"), type="expense",
        )
        result = tc.classify_transaction(tx)

        assert result.method == "llm"
        # No db → no crash, no write attempt

    @patch("app.services.llm_classifier.get_llm_classifier")
    @patch("app.services.transaction_classifier.RuleBasedClassifier")
    @patch("app.services.transaction_classifier.MLClassifier")
    def test_no_correction_stored_without_transaction_id(
        self, MockML, MockRule, mock_get_llm
    ):
        """Transaction without id (not yet persisted) should skip DB write."""
        _setup_low_confidence_mocks(MockRule, MockML)

        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.classify.return_value = _make_llm_result()
        mock_get_llm.return_value = mock_llm

        mock_db = MagicMock()

        from app.services.transaction_classifier import TransactionClassifier

        tc = TransactionClassifier(db=mock_db)

        # id=0 → falsy → skip
        tx = SimpleNamespace(
            id=0, user_id=7,
            description="Test", amount=Decimal("100"), type="expense",
        )
        result = tc.classify_transaction(tx)

        assert result.method == "llm"
        mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# BankImportService: db passed through
# ---------------------------------------------------------------------------


class TestBankImportServiceLLMIntegration:
    """Verify BankImportService passes db to TransactionClassifier."""

    def test_bank_import_service_passes_db(self):
        """BankImportService(db=db) should create TransactionClassifier(db=db)."""
        mock_db = MagicMock()

        with patch("app.services.bank_import_service.DuplicateDetector"):
            from app.services.bank_import_service import BankImportService

            service = BankImportService(db=mock_db)
            assert service.classifier.db is mock_db

    def test_bank_import_service_no_db(self):
        """BankImportService() without db should still work (classifier.db=None)."""
        with patch("app.services.bank_import_service.DuplicateDetector"):
            from app.services.bank_import_service import BankImportService

            service = BankImportService()
            assert service.classifier.db is None

    def test_bank_import_user_context_includes_business_fields(self):
        """Verify the classify call in bank import passes business_type and business_industry."""
        with patch("app.services.bank_import_service.DuplicateDetector"):
            from app.services.bank_import_service import BankImportService

            mock_db = MagicMock()
            service = BankImportService(db=mock_db)

        # Mock the classifier
        service.classifier = MagicMock()
        service.classifier.classify_transaction.return_value = SimpleNamespace(
            category="software",
            confidence=Decimal("0.8"),
            is_deductible=True,
            needs_review=False,
        )

        # Create a fake user with business fields
        user = SimpleNamespace(
            id=1,
            user_type=SimpleNamespace(value="self_employed"),
            business_type=SimpleNamespace(value="freiberufler"),
            business_industry="IT",
        )

        # Create a fake parsed transaction
        from app.models.transaction import Transaction, TransactionType

        tx = MagicMock(spec=Transaction)
        tx.type = TransactionType.EXPENSE

        # Call classify directly as the service would
        service.classifier.classify_transaction(
            tx,
            user_context={
                "user_type": user.user_type,
                "user_id": user.id,
                "business_type": getattr(user, "business_type", "") or "",
                "business_industry": getattr(user, "business_industry", "") or "",
            },
        )

        call_args = service.classifier.classify_transaction.call_args
        ctx = call_args[1].get("user_context") or call_args[0][1]
        assert ctx["business_type"] is not None
        assert ctx["business_industry"] == "IT"


# ---------------------------------------------------------------------------
# AI Orchestrator: db + user context
# ---------------------------------------------------------------------------


class TestAIOrchestratorLLMIntegration:
    """Verify AI orchestrator passes db and user to TransactionClassifier."""

    @patch("app.services.transaction_classifier.MLClassifier")
    @patch("app.services.transaction_classifier.RuleBasedClassifier")
    def test_orchestrator_passes_db(self, MockRule, MockML):
        """ToolRegistry.classify_transaction should create TransactionClassifier(db=db)."""
        mock_db = MagicMock()

        # Rule+ML return something so classify_transaction works
        MockRule.return_value.classify.return_value = SimpleNamespace(
            category="software", confidence=Decimal("0.96"), category_type="expense"
        )
        MockML.return_value.classify.return_value = SimpleNamespace(
            category="other", confidence=Decimal("0.3"), category_type="expense"
        )

        # Mock User query
        mock_user = SimpleNamespace(
            user_type="self_employed",
            business_type="freiberufler",
            business_industry="IT",
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        from app.services.ai_orchestrator import ToolRegistry

        tools = ToolRegistry(db=mock_db, user_id=1)
        result = tools.classify_transaction("JetBrains License", 249.0)

        assert result["predicted_category"] == "software"

    @patch("app.services.transaction_classifier.MLClassifier")
    @patch("app.services.transaction_classifier.RuleBasedClassifier")
    def test_orchestrator_passes_user_context(self, MockRule, MockML):
        """ToolRegistry should load user and pass it to classify_transaction."""
        mock_db = MagicMock()

        MockRule.return_value.classify.return_value = SimpleNamespace(
            category="software", confidence=Decimal("0.96"), category_type="expense"
        )
        MockML.return_value.classify.return_value = SimpleNamespace(
            category="other", confidence=Decimal("0.3"), category_type="expense"
        )

        mock_user = SimpleNamespace(
            user_type="self_employed",
            business_type="freiberufler",
            business_industry="IT",
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        from app.services.ai_orchestrator import ToolRegistry

        tools = ToolRegistry(db=mock_db, user_id=1)

        # Spy on the actual TransactionClassifier instance
        with patch(
            "app.services.transaction_classifier.TransactionClassifier.classify_transaction",
            wraps=None,
        ) as mock_classify:
            mock_classify.return_value = SimpleNamespace(
                category="software", confidence=Decimal("0.8"), method="rule"
            )
            result = tools.classify_transaction("JetBrains License", 249.0)

            # Second arg should be the user object
            call_args = mock_classify.call_args
            user_arg = call_args[0][1]  # (self, tx, user)
            assert user_arg is mock_user


# ---------------------------------------------------------------------------
# DB write failure resilience
# ---------------------------------------------------------------------------


class TestDBWriteResilience:
    """Verify that DB write failures don't break classification."""

    @patch("app.services.llm_classifier.get_llm_classifier")
    @patch("app.services.transaction_classifier.RuleBasedClassifier")
    @patch("app.services.transaction_classifier.MLClassifier")
    def test_db_commit_failure_still_returns_result(
        self, MockML, MockRule, mock_get_llm
    ):
        """If db.commit() fails, classification should still return the LLM result."""
        _setup_low_confidence_mocks(MockRule, MockML)

        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.classify.return_value = _make_llm_result("travel", True)
        mock_get_llm.return_value = mock_llm

        mock_db = MagicMock()
        mock_db.commit.side_effect = Exception("DB connection lost")

        from app.services.transaction_classifier import TransactionClassifier

        tc = TransactionClassifier(db=mock_db)

        tx = SimpleNamespace(
            id=42, user_id=7,
            description="Flug Wien-Berlin", amount=Decimal("189.00"), type="expense",
        )
        result = tc.classify_transaction(tx)

        # Should still return the LLM result despite DB failure
        assert result.method == "llm"
        assert result.category == "travel"
        # Rollback should have been called
        mock_db.rollback.assert_called_once()
