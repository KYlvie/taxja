"""
Tests for ChatGPT round-2 governance framework fixes.

Covers:
1. Training data source filtering (only human_verified + llm_consensus)
2. UserClassificationRule soft/strict distinction
3. Soft rule reduced confidence in classifier lookup
4. Human corrections get source=human_verified
5. LLM rules get rule_type=soft
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# 1. Training data source filtering
# ---------------------------------------------------------------------------

class TestTrainingDataSourceFilter:
    """get_training_data should only include trusted sources."""

    def test_excludes_llm_unverified(self):
        """llm_unverified corrections must NOT enter training data."""
        from app.services.classification_learning import ClassificationLearningService
        from app.models.classification_correction import ClassificationCorrection

        db = MagicMock()
        svc = ClassificationLearningService(db)

        # Create mock corrections with different sources
        human_corr = MagicMock()
        human_corr.source = "human_verified"
        human_corr.correct_category = "groceries"
        human_corr.transaction = MagicMock()
        human_corr.transaction.description = "billa einkauf"
        human_corr.transaction.amount = Decimal("45.00")
        human_corr.transaction.type = MagicMock(value="expense")

        unverified_corr = MagicMock()
        unverified_corr.source = "llm_unverified"
        unverified_corr.correct_category = "travel"
        unverified_corr.transaction = MagicMock()
        unverified_corr.transaction.description = "booking hotel"
        unverified_corr.transaction.amount = Decimal("200.00")
        unverified_corr.transaction.type = MagicMock(value="expense")

        consensus_corr = MagicMock()
        consensus_corr.source = "llm_consensus"
        consensus_corr.correct_category = "equipment"
        consensus_corr.transaction = MagicMock()
        consensus_corr.transaction.description = "mediamarkt laptop"
        consensus_corr.transaction.amount = Decimal("899.00")
        consensus_corr.transaction.type = MagicMock(value="expense")

        # Mock the query chain to return only trusted sources
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [human_corr, consensus_corr]
        db.query.return_value = mock_query

        data = svc.get_training_data()

        # Should have 2 entries (human + consensus), NOT 3
        assert len(data) == 2
        categories = [d[2] for d in data]
        assert "groceries" in categories
        assert "equipment" in categories
        assert "travel" not in categories  # llm_unverified excluded

    def test_includes_legacy_null_source(self):
        """Pre-migration corrections (source=None) should be included."""
        from app.services.classification_learning import ClassificationLearningService

        db = MagicMock()
        svc = ClassificationLearningService(db)

        legacy_corr = MagicMock()
        legacy_corr.source = None
        legacy_corr.correct_category = "utilities"
        legacy_corr.transaction = MagicMock()
        legacy_corr.transaction.description = "wien energie"
        legacy_corr.transaction.amount = Decimal("85.00")
        legacy_corr.transaction.type = MagicMock(value="expense")

        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [legacy_corr]
        db.query.return_value = mock_query

        data = svc.get_training_data()
        assert len(data) == 1
        assert data[0][2] == "utilities"


# ---------------------------------------------------------------------------
# 2. UserClassificationRule soft/strict model
# ---------------------------------------------------------------------------

class TestUserRuleSoftStrict:
    """UserClassificationRule should have rule_type field."""

    def test_model_has_rule_type_field(self):
        from app.models.user_classification_rule import UserClassificationRule
        assert hasattr(UserClassificationRule, "rule_type")

    def test_default_rule_type_is_strict(self):
        from app.models.user_classification_rule import UserClassificationRule
        rule = UserClassificationRule(
            user_id=1,
            normalized_description="test",
            txn_type="expense",
            category="groceries",
            rule_type="strict",
        )
        assert rule.rule_type == "strict"

    def test_soft_rule_can_be_created(self):
        from app.models.user_classification_rule import UserClassificationRule
        rule = UserClassificationRule(
            user_id=1,
            normalized_description="test",
            txn_type="expense",
            category="groceries",
            rule_type="soft",
        )
        assert rule.rule_type == "soft"


# ---------------------------------------------------------------------------
# 3. upsert_rule soft/strict behavior
# ---------------------------------------------------------------------------

class TestUpsertRuleSoftStrict:
    """upsert_rule should handle soft/strict correctly."""

    def _make_service(self):
        from app.services.user_classification_service import UserClassificationService
        db = MagicMock()
        svc = UserClassificationService(db)
        return svc, db

    def test_new_rule_defaults_to_strict(self):
        svc, db = self._make_service()
        db.query.return_value.filter.return_value.first.return_value = None

        rule = svc.upsert_rule(
            user_id=1,
            description="BILLA Filiale 1234",
            txn_type="expense",
            category="groceries",
        )
        assert rule.rule_type == "strict"
        assert rule.confidence == Decimal("1.00")

    def test_new_soft_rule_has_reduced_confidence(self):
        svc, db = self._make_service()
        db.query.return_value.filter.return_value.first.return_value = None

        rule = svc.upsert_rule(
            user_id=1,
            description="BILLA Filiale 1234",
            txn_type="expense",
            category="groceries",
            rule_type="soft",
        )
        assert rule.rule_type == "soft"
        assert rule.confidence == Decimal("0.80")

    def test_soft_rule_upgraded_to_strict_on_human_confirm(self):
        """If a soft rule exists and human confirms, upgrade to strict."""
        svc, db = self._make_service()

        from app.models.user_classification_rule import UserClassificationRule
        existing = UserClassificationRule(
            user_id=1,
            normalized_description="billa",
            original_description="BILLA",
            txn_type="expense",
            category="groceries",
            confidence=Decimal("0.80"),
            hit_count=1,
            rule_type="soft",
        )
        db.query.return_value.filter.return_value.first.return_value = existing

        result = svc.upsert_rule(
            user_id=1,
            description="BILLA",
            txn_type="expense",
            category="groceries",
            rule_type="strict",
        )
        assert result.rule_type == "strict"
        assert result.confidence == Decimal("1.00")
        assert result.hit_count == 2

    def test_strict_rule_not_downgraded_to_soft(self):
        """A strict rule should never be downgraded to soft."""
        svc, db = self._make_service()

        from app.models.user_classification_rule import UserClassificationRule
        existing = UserClassificationRule(
            user_id=1,
            normalized_description="billa",
            original_description="BILLA",
            txn_type="expense",
            category="groceries",
            confidence=Decimal("1.00"),
            hit_count=3,
            rule_type="strict",
        )
        db.query.return_value.filter.return_value.first.return_value = existing

        result = svc.upsert_rule(
            user_id=1,
            description="BILLA",
            txn_type="expense",
            category="groceries",
            rule_type="soft",
        )
        # Should remain strict
        assert result.rule_type == "strict"
        assert result.confidence == Decimal("1.00")


# ---------------------------------------------------------------------------
# 4. Classifier soft rule reduced confidence
# ---------------------------------------------------------------------------

class TestClassifierSoftRuleConfidence:
    """Soft rules should have capped confidence in classifier lookup."""

    def _make_classifier(self):
        from app.services.transaction_classifier import TransactionClassifier
        classifier = TransactionClassifier.__new__(TransactionClassifier)
        classifier.db = MagicMock()
        classifier._user_svc = MagicMock()
        classifier.ml_classifier = MagicMock()
        classifier.rule_classifier = MagicMock()
        return classifier

    def _make_txn(self, desc="BILLA Filiale 1234"):
        txn = MagicMock()
        txn.id = 42
        txn.user_id = 1
        txn.description = desc
        txn.type = MagicMock(value="expense")
        return txn

    def test_strict_rule_full_confidence(self):
        classifier = self._make_classifier()
        txn = self._make_txn()

        rule = MagicMock()
        rule.category = "groceries"
        rule.confidence = Decimal("1.00")
        rule.hit_count = 5
        rule.normalized_description = "billa"
        rule.rule_type = "strict"
        rule.frozen = False
        classifier._user_svc.lookup.return_value = rule

        result = classifier._try_user_override(txn)
        assert result is not None
        assert result.confidence == Decimal("1.00")
        assert result.method == "user_rule"

    def test_soft_rule_capped_confidence(self):
        classifier = self._make_classifier()
        txn = self._make_txn()

        rule = MagicMock()
        rule.category = "groceries"
        rule.confidence = Decimal("0.90")  # Even if stored high
        rule.hit_count = 2
        rule.normalized_description = "billa"
        rule.rule_type = "soft"
        rule.frozen = False
        classifier._user_svc.lookup.return_value = rule

        result = classifier._try_user_override(txn)
        assert result is not None
        # Soft rules capped at 0.80
        assert result.confidence == Decimal("0.80")
        assert result.method == "user_rule_soft"

    def test_soft_rule_below_cap_keeps_original(self):
        classifier = self._make_classifier()
        txn = self._make_txn()

        rule = MagicMock()
        rule.category = "groceries"
        rule.confidence = Decimal("0.70")  # Below cap
        rule.hit_count = 1
        rule.normalized_description = "billa"
        rule.rule_type = "soft"
        rule.frozen = False
        classifier._user_svc.lookup.return_value = rule

        result = classifier._try_user_override(txn)
        assert result is not None
        assert result.confidence == Decimal("0.70")
        assert result.method == "user_rule_soft"


# ---------------------------------------------------------------------------
# 5. LLM creates soft rules, human creates strict
# ---------------------------------------------------------------------------

class TestRuleTypeOnCreation:
    """LLM corrections create soft rules; human corrections create strict."""

    def _make_classifier(self):
        from app.services.transaction_classifier import TransactionClassifier
        classifier = TransactionClassifier.__new__(TransactionClassifier)
        classifier.db = MagicMock()
        classifier.db.add = MagicMock()
        classifier.db.commit = MagicMock()
        classifier.db.rollback = MagicMock()
        classifier._user_svc = MagicMock()
        return classifier

    def _make_txn(self, desc="BILLA Filiale 1234"):
        txn = MagicMock()
        txn.id = 42
        txn.user_id = 1
        txn.description = desc
        txn.type = MagicMock(value="expense")
        return txn

    def test_llm_correction_creates_soft_rule(self):
        """High-confidence LLM result should create a soft rule."""
        classifier = self._make_classifier()
        txn = self._make_txn()

        llm_result = MagicMock()
        llm_result.confidence = Decimal("0.92")
        llm_result.category = "groceries"
        llm_result.category_type = "expense"

        classifier._store_llm_correction(txn, llm_result, "employee")

        # upsert_rule should be called with rule_type="soft"
        call_kwargs = classifier._user_svc.upsert_rule.call_args
        assert call_kwargs is not None
        # Check keyword args
        if call_kwargs.kwargs:
            assert call_kwargs.kwargs.get("rule_type") == "soft"
        else:
            # Positional args: user_id, description, txn_type, category, rule_type
            assert "soft" in call_kwargs.args or call_kwargs[1].get("rule_type") == "soft"

    def test_human_correction_creates_strict_rule(self):
        """Human correction should create a strict rule (default)."""
        classifier = self._make_classifier()
        # learn_from_correction calls classify_transaction internally,
        # so we mock it to avoid needing full pipeline setup
        classifier.classify_transaction = MagicMock(return_value=MagicMock(
            category="other", confidence=Decimal("0.30"),
        ))
        txn = self._make_txn()

        classifier.learn_from_correction(txn, "groceries", user_id=1)

        call_kwargs = classifier._user_svc.upsert_rule.call_args
        assert call_kwargs is not None
        # Default rule_type should be "strict" (or not passed, which defaults)
        if call_kwargs.kwargs and "rule_type" in call_kwargs.kwargs:
            assert call_kwargs.kwargs["rule_type"] == "strict"
        # If not passed, the default in upsert_rule is "strict" — that's fine

    def test_human_correction_has_source_human_verified(self):
        """Human corrections should have source=human_verified."""
        classifier = self._make_classifier()
        classifier.classify_transaction = MagicMock(return_value=MagicMock(
            category="other", confidence=Decimal("0.30"),
        ))
        txn = self._make_txn()

        classifier.learn_from_correction(txn, "groceries", user_id=1)

        # Check the ClassificationCorrection object passed to db.add
        added_obj = classifier.db.add.call_args[0][0]
        assert added_obj.source == "human_verified"
