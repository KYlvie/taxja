"""
Tests for the classification pipeline improvements:
1. ML model versioning (backup / rollback)
2. Classification learning service (timestamp-based correction counting)
3. LLM classifier Redis cache (with in-memory fallback)
4. Celery auto-retrain task
"""
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockTransaction:
    """Minimal transaction for testing."""
    def __init__(self, description="Test", amount=Decimal("100"), txn_type="expense",
                 id=1, user_id=1):
        self.id = id
        self.user_id = user_id
        self.description = description
        self.amount = amount
        self.type = txn_type


SAMPLE_TRAINING_DATA = [
    ("BILLA supermarket", 45.0, "groceries", "expense"),
    ("SPAR shopping", 60.0, "groceries", "expense"),
    ("HOFER groceries", 35.0, "groceries", "expense"),
    ("LIDL store", 40.0, "groceries", "expense"),
    ("MERKUR market", 55.0, "groceries", "expense"),
    ("OBI hardware", 120.0, "maintenance", "expense"),
    ("Baumax supplies", 85.0, "maintenance", "expense"),
    ("Repair materials", 95.0, "maintenance", "expense"),
    ("Office paper", 30.0, "office_supplies", "expense"),
    ("Printer ink", 45.0, "office_supplies", "expense"),
    ("Stationery", 25.0, "office_supplies", "expense"),
    ("Business trip", 150.0, "travel", "expense"),
]


# ===========================================================================
# 1. ML Model Versioning
# ===========================================================================

class TestMLModelVersioning:
    """Tests for MLClassifier versioning: backup, list, rollback, prune."""

    @pytest.fixture(autouse=True)
    def setup_tmp_model_dir(self, tmp_path):
        self.model_dir = str(tmp_path / "models")
        os.makedirs(self.model_dir, exist_ok=True)

    def _make_classifier(self):
        from app.services.ml_classifier import MLClassifier
        return MLClassifier(model_path=self.model_dir)

    # -- backup & list --

    def test_backup_with_no_existing_models_returns_none(self):
        clf = self._make_classifier()
        assert clf._backup_current_models() is None

    def test_backup_creates_version_dir(self):
        clf = self._make_classifier()
        clf.train_model(SAMPLE_TRAINING_DATA)
        # Models saved on disk now
        version = clf._backup_current_models()
        assert version is not None
        assert os.path.isdir(clf._version_dir(version))

    def test_list_versions_returns_newest_first(self):
        clf = self._make_classifier()
        clf.train_model(SAMPLE_TRAINING_DATA)

        v1 = clf._backup_current_models()
        time.sleep(1.1)  # ensure distinct timestamp (resolution is seconds)
        v2 = clf._backup_current_models()

        versions = clf.list_versions()
        assert len(versions) >= 2
        assert versions[0] >= versions[1]  # newest first

    def test_save_models_auto_backs_up_previous(self):
        clf = self._make_classifier()
        clf.train_model(SAMPLE_TRAINING_DATA)  # first save
        # second save triggers auto-backup of the first
        clf.train_model(SAMPLE_TRAINING_DATA)

        versions = clf.list_versions()
        assert len(versions) >= 1

    # -- rollback --

    def test_rollback_restores_model_files(self):
        """
        Verify rollback copies the correct version's files back to the model dir.

        Instead of relying on pickle byte-level identity (which can vary due to
        internal Python state), we create simple known-content files, back them up,
        overwrite them, and verify rollback restores the originals.
        """
        clf = self._make_classifier()
        os.makedirs(self.model_dir, exist_ok=True)

        # Create fake "V1" model files with known content
        v1_content = {
            "expense_model.pkl": b"V1-MODEL-DATA",
            "expense_vectorizer.pkl": b"V1-VECTORIZER-DATA",
            "amount_scaler.pkl": b"V1-SCALER-DATA",
        }
        for fname, data in v1_content.items():
            with open(os.path.join(self.model_dir, fname), "wb") as f:
                f.write(data)

        # Back up V1
        v1_label = clf._backup_current_models()
        assert v1_label is not None

        # Overwrite with "V2" content
        for fname in v1_content:
            with open(os.path.join(self.model_dir, fname), "wb") as f:
                f.write(b"V2-DIFFERENT-DATA")

        # Verify current files are V2
        for fname in v1_content:
            with open(os.path.join(self.model_dir, fname), "rb") as f:
                assert f.read() == b"V2-DIFFERENT-DATA"

        # Rollback to V1
        assert clf.rollback(v1_label) is True

        # Verify files are restored to V1 content
        for fname, expected in v1_content.items():
            with open(os.path.join(self.model_dir, fname), "rb") as f:
                assert f.read() == expected, f"{fname} not restored correctly"

    def test_rollback_nonexistent_version_returns_false(self):
        clf = self._make_classifier()
        assert clf.rollback("nonexistent") is False

    # -- prune --

    def test_prune_keeps_max_versions(self):
        from app.services.ml_classifier import _MAX_MODEL_VERSIONS

        clf = self._make_classifier()
        clf.train_model(SAMPLE_TRAINING_DATA)

        # Create more versions than the limit
        for _ in range(_MAX_MODEL_VERSIONS + 3):
            clf._backup_current_models()
            time.sleep(0.05)

        clf._prune_old_versions()
        versions = clf.list_versions()
        assert len(versions) <= _MAX_MODEL_VERSIONS


# ===========================================================================
# 2. Classification Learning Service — timestamp filtering
# ===========================================================================

class TestClassificationLearningTimestamp:
    """Tests that correction counting respects last_trained_at."""

    @pytest.fixture(autouse=True)
    def setup_tmp_model_dir(self, tmp_path):
        self.model_dir = str(tmp_path / "models")
        os.makedirs(self.model_dir, exist_ok=True)

    def _make_service(self, db):
        from app.services.classification_learning import ClassificationLearningService
        return ClassificationLearningService(db=db, model_path=self.model_dir)

    # -- last_trained_at persistence --

    def test_get_last_trained_at_returns_none_initially(self):
        svc = self._make_service(db=MagicMock())
        assert svc.get_last_trained_at() is None

    def test_save_and_load_last_trained_at(self):
        svc = self._make_service(db=MagicMock())
        now = datetime.now(timezone.utc)
        svc._save_last_trained_at(now)

        loaded = svc.get_last_trained_at()
        assert loaded is not None
        # Compare within 1 second tolerance
        assert abs((loaded - now).total_seconds()) < 1

    def test_last_trained_at_file_survives_new_instance(self):
        db = MagicMock()
        svc1 = self._make_service(db)
        now = datetime.now(timezone.utc)
        svc1._save_last_trained_at(now)

        svc2 = self._make_service(db)
        loaded = svc2.get_last_trained_at()
        assert loaded is not None

    # -- corrections_since_last_training --

    def test_no_training_yet_returns_total_count(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 42
        svc = self._make_service(db)

        assert svc.get_corrections_since_last_training() == 42

    def test_with_training_timestamp_filters_by_date(self):
        db = MagicMock()
        svc = self._make_service(db)

        # Save a training timestamp
        svc._save_last_trained_at(datetime.now(timezone.utc))

        # Mock the filtered query
        db.query.return_value.filter.return_value.count.return_value = 7
        result = svc.get_corrections_since_last_training()
        assert result == 7

    # -- should_retrain --

    def test_should_retrain_false_below_threshold(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 10
        svc = self._make_service(db)
        assert svc.should_retrain() is False

    def test_should_retrain_true_above_threshold(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 100
        svc = self._make_service(db)
        assert svc.should_retrain() is True

    # -- retrain_model saves timestamp --

    def test_retrain_model_saves_timestamp_on_success(self):
        db = MagicMock()
        svc = self._make_service(db)

        # Stub get_training_data to return enough data
        svc.get_training_data = MagicMock(return_value=SAMPLE_TRAINING_DATA)

        assert svc.get_last_trained_at() is None
        result = svc.retrain_model()
        assert result is True
        assert svc.get_last_trained_at() is not None

    def test_retrain_model_does_not_save_timestamp_on_failure(self):
        db = MagicMock()
        svc = self._make_service(db)

        # Not enough data → training fails
        svc.get_training_data = MagicMock(return_value=[])

        result = svc.retrain_model()
        assert result is False
        assert svc.get_last_trained_at() is None

    # -- auto_retrain_if_needed --

    def test_auto_retrain_returns_new_corrections_field(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 10  # below threshold
        svc = self._make_service(db)

        result = svc.auto_retrain_if_needed()
        assert result["retrained"] is False
        assert "new_corrections" in result
        assert "total_corrections" in result


# ===========================================================================
# 3. LLM Classifier — Redis cache with fallback
# ===========================================================================

class TestLLMClassifierCache:
    """Tests for _RedisClassificationCache and LLMTransactionClassifier caching."""

    def test_memory_fallback_when_redis_unavailable(self):
        """Cache should work with in-memory fallback when Redis is down."""
        from app.services.llm_classifier import _RedisClassificationCache, LLMClassificationResult

        # Force no Redis by patching
        with patch("app.services.llm_classifier._RedisClassificationCache._connect"):
            cache = _RedisClassificationCache(ttl=60)
            cache._redis = None  # simulate Redis unavailable

        result = LLMClassificationResult(
            category="groceries",
            confidence=Decimal("0.75"),
            category_type="expense",
            is_deductible=False,
            deduction_reason="Private consumption",
        )

        # Set and get
        cache.set("test_key", result)
        cached = cache.get("test_key")

        assert cached is not None
        assert cached.category == "groceries"
        assert cached.confidence == Decimal("0.75")
        assert cached.is_deductible is False

    def test_memory_cache_miss_returns_none(self):
        from app.services.llm_classifier import _RedisClassificationCache

        with patch("app.services.llm_classifier._RedisClassificationCache._connect"):
            cache = _RedisClassificationCache(ttl=60)
            cache._redis = None

        assert cache.get("nonexistent") is None

    def test_memory_cache_stats(self):
        from app.services.llm_classifier import _RedisClassificationCache, LLMClassificationResult

        with patch("app.services.llm_classifier._RedisClassificationCache._connect"):
            cache = _RedisClassificationCache(ttl=60)
            cache._redis = None

        result = LLMClassificationResult(
            category="groceries", confidence=Decimal("0.75"),
            category_type="expense",
        )
        cache.set("k1", result)
        cache.set("k2", result)

        stats = cache.stats()
        assert stats["backend"] == "memory"
        assert stats["total"] == 2
        assert stats["active"] == 2

    def test_memory_cache_eviction(self):
        from app.services.llm_classifier import _RedisClassificationCache, LLMClassificationResult

        with patch("app.services.llm_classifier._RedisClassificationCache._connect"):
            cache = _RedisClassificationCache(ttl=60, max_memory_size=5)
            cache._redis = None

        result = LLMClassificationResult(
            category="groceries", confidence=Decimal("0.75"),
            category_type="expense",
        )

        # Fill beyond max
        for i in range(10):
            cache.set(f"key_{i}", result)

        stats = cache.stats()
        assert stats["total"] <= 5

    def test_redis_serialization_roundtrip(self):
        """Test that Redis set/get properly serializes/deserializes."""
        from app.services.llm_classifier import _RedisClassificationCache, LLMClassificationResult

        with patch("app.services.llm_classifier._RedisClassificationCache._connect"):
            cache = _RedisClassificationCache(ttl=60)

        # Simulate Redis with a dict
        redis_mock = MagicMock()
        store = {}

        def mock_setex(key, ttl, value):
            store[key] = value

        def mock_get(key):
            return store.get(key)

        redis_mock.setex = mock_setex
        redis_mock.get = mock_get
        cache._redis = redis_mock

        original = LLMClassificationResult(
            category="professional_services",
            confidence=Decimal("0.75"),
            category_type="expense",
            is_deductible=True,
            deduction_reason="Betriebsausgabe für IT-Beratung",
        )

        cache.set("test_redis", original)
        loaded = cache.get("test_redis")

        assert loaded is not None
        assert loaded.category == "professional_services"
        assert loaded.confidence == Decimal("0.75")
        assert loaded.is_deductible is True
        assert loaded.deduction_reason == "Betriebsausgabe für IT-Beratung"
        assert loaded.cached is True

    def test_classifier_cache_key_includes_user_context(self):
        """Different user profiles should produce different cache keys."""
        from app.services.llm_classifier import LLMTransactionClassifier

        clf = LLMTransactionClassifier.__new__(LLMTransactionClassifier)

        key1 = clf._build_cache_key("billa", "expense", "employee", "", "")
        key2 = clf._build_cache_key("billa", "expense", "self_employed", "freiberufler", "gastronomie")
        key3 = clf._build_cache_key("billa", "expense", "self_employed", "freiberufler", "IT")

        assert key1 != key2
        assert key2 != key3
        assert key1 != key3

    def test_classifier_cache_key_same_for_same_input(self):
        from app.services.llm_classifier import LLMTransactionClassifier

        clf = LLMTransactionClassifier.__new__(LLMTransactionClassifier)

        key_a = clf._build_cache_key("billa", "expense", "employee", "", "")
        key_b = clf._build_cache_key("billa", "expense", "employee", "", "")

        assert key_a == key_b

    def test_merchant_normalization(self):
        from app.services.llm_classifier import LLMTransactionClassifier

        norm = LLMTransactionClassifier._normalize_merchant

        # Filiale + number stripped, city name kept
        result = norm("BILLA FILIALE 1234 WIEN")
        assert "billa" in result
        assert "filiale" not in result
        assert "1234" not in result

        # Prefix stripped
        assert norm("Lastschrift SPAR") == "spar"

        # Prefix stripped
        result = norm("Überweisung an Dr. Schmidt")
        assert "dr. schmidt" in result
        assert "überweisung" not in result


# ===========================================================================
# 4. Celery Auto-Retrain Task
# ===========================================================================

class TestAutoRetrainLogic:
    """
    Tests for the auto-retrain logic.

    We test the ClassificationLearningService.auto_retrain_if_needed()
    directly rather than going through the Celery task wrapper, since
    the task is just a thin shell around this service method.
    """

    @pytest.fixture(autouse=True)
    def setup_tmp_model_dir(self, tmp_path):
        self.model_dir = str(tmp_path / "models")
        os.makedirs(self.model_dir, exist_ok=True)

    def test_skips_when_not_enough_corrections(self):
        """Should return retrained=False when below threshold."""
        from app.services.classification_learning import ClassificationLearningService

        db = MagicMock()
        db.query.return_value.count.return_value = 10  # below 50
        svc = ClassificationLearningService(db=db, model_path=self.model_dir)

        result = svc.auto_retrain_if_needed()

        assert result["retrained"] is False
        assert result["new_corrections"] == 10
        assert result["min_required"] == 50

    def test_retrains_when_enough_corrections(self):
        """Should retrain and return retrained=True."""
        from app.services.classification_learning import ClassificationLearningService

        db = MagicMock()
        db.query.return_value.count.return_value = 60  # above 50
        svc = ClassificationLearningService(db=db, model_path=self.model_dir)

        # Stub training data
        svc.get_training_data = MagicMock(return_value=SAMPLE_TRAINING_DATA)

        result = svc.auto_retrain_if_needed()

        assert result["retrained"] is True
        assert "last_trained_at" in result
        assert result["last_trained_at"] is not None

    def test_retrain_failure_returns_reason(self):
        """Should return reason when retraining fails (not enough samples)."""
        from app.services.classification_learning import ClassificationLearningService

        db = MagicMock()
        db.query.return_value.count.return_value = 60
        svc = ClassificationLearningService(db=db, model_path=self.model_dir)

        # Empty training data → training fails
        svc.get_training_data = MagicMock(return_value=[])

        result = svc.auto_retrain_if_needed()

        assert result["retrained"] is False
        assert result["reason"] == "Retraining failed"

    def test_celery_task_module_imports_correctly(self):
        """Verify the Celery task module can be imported without errors."""
        from app.tasks.classification_tasks import auto_retrain_classification_model
        assert auto_retrain_classification_model.name == "classification.auto_retrain"


# ===========================================================================
# 5. Integration: TransactionClassifier stores LLM result → correction
# ===========================================================================

class TestTransactionClassifierLLMFeedback:
    """Ensure LLM results are stored as ClassificationCorrection records."""

    def test_store_llm_correction_called_on_llm_classify(self):
        from app.services.transaction_classifier import TransactionClassifier

        db = MagicMock()
        clf = TransactionClassifier(db=db)
        # Disable user-override so it falls through to rule → ML → LLM
        clf._user_svc = MagicMock()
        clf._user_svc.lookup.return_value = None

        txn = MockTransaction(
            description="Unknown Merchant XYZ",
            amount=Decimal("99.99"),
            txn_type="expense",
            id=42,
            user_id=7,
        )

        # Mock the LLM classifier to return a result
        mock_llm_result = MagicMock()
        mock_llm_result.category = "professional_services"
        mock_llm_result.confidence = Decimal("0.75")
        mock_llm_result.category_type = "expense"
        mock_llm_result.is_deductible = True
        mock_llm_result.deduction_reason = "IT Beratung"
        mock_llm_result.cached = False

        # Patch where it's imported (lazy import inside _try_llm_classify)
        with patch("app.services.llm_classifier.get_llm_classifier") as mock_get:
            mock_llm = mock_get.return_value
            mock_llm.is_available = True
            mock_llm.classify.return_value = mock_llm_result

            # Force low confidence from rule + ML so LLM is triggered
            clf.rule_classifier.classify = MagicMock(
                return_value=MagicMock(
                    category="other", confidence=Decimal("0.2"), category_type="expense"
                )
            )
            clf.ml_classifier.classify = MagicMock(
                return_value=MagicMock(
                    category="other", confidence=Decimal("0.3"), category_type="expense"
                )
            )

            result = clf.classify_transaction(txn, user_context={"user_type": "self_employed"})

        assert result.method == "llm"
        assert result.category == "professional_services"

        # Verify correction was stored
        db.add.assert_called_once()
        db.commit.assert_called_once()
        correction = db.add.call_args[0][0]
        assert correction.correct_category == "professional_services"
        assert correction.transaction_id == 42
        assert correction.user_id == 7
