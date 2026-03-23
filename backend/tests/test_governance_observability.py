"""
Tests for governance observability (Task 18):
1. GovernanceMetricsService — unified metrics
2. UserClassificationRule lifecycle (decay, conflict, freeze, archive)
3. Training data audit report
4. Classifier integration: last_hit_at recording, frozen rule skip, conflict recording
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# 1. GovernanceMetricsService
# ---------------------------------------------------------------------------

class TestGovernanceMetricsEmpty:
    """Metrics on empty DB should return zero-filled dicts."""

    def test_rule_metrics_empty(self):
        from app.services.governance_metrics import GovernanceMetricsService
        db = MagicMock()
        svc = GovernanceMetricsService(db)

        q = MagicMock()
        q.count.return_value = 0
        db.query.return_value = q

        result = svc.get_rule_metrics()
        assert result["total_rules"] == 0
        assert result["strict_hit_rate"] == 0.0
        assert result["soft_hit_rate"] == 0.0

    def test_correction_source_metrics_empty(self):
        from app.services.governance_metrics import GovernanceMetricsService
        db = MagicMock()
        svc = GovernanceMetricsService(db)

        mock_q = MagicMock()
        mock_q.group_by.return_value = mock_q
        mock_q.all.return_value = []
        db.query.return_value = mock_q

        result = svc.get_correction_source_metrics()
        assert result["total_corrections"] == 0
        assert result["trainable_count"] == 0
        assert result["human_verified_ratio"] == 0.0


class TestGovernanceMetricsWithData:
    """Metrics with mock data."""

    def test_correction_source_distribution(self):
        from app.services.governance_metrics import GovernanceMetricsService
        db = MagicMock()
        svc = GovernanceMetricsService(db)

        mock_q = MagicMock()
        mock_q.group_by.return_value = mock_q
        mock_q.all.return_value = [
            ("human_verified", 80),
            ("llm_verified", 15),
            ("llm_unverified", 25),
            ("llm_consensus", 20),
            (None, 10),  # legacy
        ]
        db.query.return_value = mock_q

        result = svc.get_correction_source_metrics()
        assert result["total_corrections"] == 150
        assert result["human_verified_count"] == 80
        assert result["llm_unverified_count"] == 25
        assert result["legacy_null_count"] == 10
        # trainable = human_verified(80) + llm_consensus(20) + legacy(10) = 110
        assert result["trainable_count"] == 110
        assert result["excluded_count"] == 40

    def test_full_report_structure(self):
        from app.services.governance_metrics import GovernanceMetricsService
        db = MagicMock()
        svc = GovernanceMetricsService(db)

        # Mock everything to return empty
        q = MagicMock()
        q.count.return_value = 0
        q.group_by.return_value = q
        q.all.return_value = []
        q.filter.return_value = q
        q.scalar.return_value = 0
        db.query.return_value = q

        report = svc.get_full_report()
        assert "rules" in report
        assert "corrections" in report
        assert "soft_to_strict_upgrades" in report


# ---------------------------------------------------------------------------
# 2. Rule lifecycle: conflict, freeze, decay, archive
# ---------------------------------------------------------------------------

class TestRuleConflict:
    """record_conflict increments count and freezes at threshold."""

    def test_conflict_increments(self):
        from app.services.user_classification_service import UserClassificationService
        from app.models.user_classification_rule import UserClassificationRule

        db = MagicMock()
        svc = UserClassificationService(db)

        rule = UserClassificationRule(
            user_id=1, normalized_description="test", txn_type="expense",
            category="groceries", rule_type="soft", conflict_count=0, frozen=False,
        )
        svc.record_conflict(rule)
        assert rule.conflict_count == 1
        assert rule.frozen is False

    def test_soft_rule_freezes_at_3_conflicts(self):
        from app.services.user_classification_service import UserClassificationService
        from app.models.user_classification_rule import UserClassificationRule

        db = MagicMock()
        svc = UserClassificationService(db)

        rule = UserClassificationRule(
            user_id=1, normalized_description="test", txn_type="expense",
            category="groceries", rule_type="soft", conflict_count=2, frozen=False,
        )
        svc.record_conflict(rule)
        assert rule.conflict_count == 3
        assert rule.frozen is True

    def test_strict_rule_does_not_freeze(self):
        from app.services.user_classification_service import UserClassificationService
        from app.models.user_classification_rule import UserClassificationRule

        db = MagicMock()
        svc = UserClassificationService(db)

        rule = UserClassificationRule(
            user_id=1, normalized_description="test", txn_type="expense",
            category="groceries", rule_type="strict", conflict_count=2, frozen=False,
        )
        svc.record_conflict(rule)
        assert rule.conflict_count == 3
        assert rule.frozen is False  # strict rules don't auto-freeze


class TestRuleDecay:
    """decay_stale_soft_rules reduces confidence of old soft rules."""

    def test_decays_stale_soft_rule(self):
        from app.services.user_classification_service import UserClassificationService
        from app.models.user_classification_rule import UserClassificationRule

        db = MagicMock()
        svc = UserClassificationService(db)

        stale_rule = UserClassificationRule(
            user_id=1, normalized_description="old", txn_type="expense",
            category="groceries", rule_type="soft", confidence=Decimal("0.80"),
            frozen=False, last_hit_at=None,
        )

        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.all.return_value = [stale_rule]
        db.query.return_value = mock_q

        count = svc.decay_stale_soft_rules(user_id=1, stale_days=90)
        assert count == 1
        assert stale_rule.confidence == Decimal("0.70")

    def test_decay_floors_at_050(self):
        from app.services.user_classification_service import UserClassificationService
        from app.models.user_classification_rule import UserClassificationRule

        db = MagicMock()
        svc = UserClassificationService(db)

        rule = UserClassificationRule(
            user_id=1, normalized_description="old", txn_type="expense",
            category="groceries", rule_type="soft", confidence=Decimal("0.50"),
            frozen=False, last_hit_at=None,
        )

        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.all.return_value = [rule]
        db.query.return_value = mock_q

        count = svc.decay_stale_soft_rules(user_id=1)
        assert count == 0  # already at floor, no change
        assert rule.confidence == Decimal("0.50")


class TestRuleArchive:
    """archive_low_hit_rules deletes old low-hit rules."""

    def test_archive_returns_count(self):
        from app.services.user_classification_service import UserClassificationService

        db = MagicMock()
        svc = UserClassificationService(db)

        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.delete.return_value = 3
        db.query.return_value = mock_q

        count = svc.archive_low_hit_rules(user_id=1, min_hits=1, stale_days=180)
        assert count == 3


# ---------------------------------------------------------------------------
# 3. Training audit report
# ---------------------------------------------------------------------------

class TestTrainingAuditReport:
    """get_training_audit_report returns source distribution."""

    def test_report_structure(self):
        from app.services.classification_learning import ClassificationLearningService

        db = MagicMock()
        svc = ClassificationLearningService(db)

        mock_q = MagicMock()
        mock_q.group_by.return_value = mock_q
        mock_q.all.return_value = [
            ("human_verified", 50),
            ("llm_unverified", 10),
            (None, 5),
        ]
        db.query.return_value = mock_q

        report = svc.get_training_audit_report()
        assert report["total_corrections"] == 65
        assert report["trainable_count"] == 55  # human(50) + legacy(5)
        assert report["excluded_count"] == 10
        assert report["ready_to_retrain"] is True  # 55 >= 50
        assert "human_verified" in report["by_source"]
        assert "legacy_null" in report["by_source"]
        assert report["by_source"]["human_verified"]["count"] == 50

    def test_empty_report(self):
        from app.services.classification_learning import ClassificationLearningService

        db = MagicMock()
        svc = ClassificationLearningService(db)

        mock_q = MagicMock()
        mock_q.group_by.return_value = mock_q
        mock_q.all.return_value = []
        db.query.return_value = mock_q

        report = svc.get_training_audit_report()
        assert report["total_corrections"] == 0
        assert report["trainable_count"] == 0
        assert report["ready_to_retrain"] is False
        assert report["net_trainable_ratio"] == 0.0

    def test_not_ready_when_below_threshold(self):
        from app.services.classification_learning import ClassificationLearningService

        db = MagicMock()
        svc = ClassificationLearningService(db)

        mock_q = MagicMock()
        mock_q.group_by.return_value = mock_q
        mock_q.all.return_value = [("human_verified", 10)]
        db.query.return_value = mock_q

        report = svc.get_training_audit_report()
        assert report["trainable_count"] == 10
        assert report["ready_to_retrain"] is False


# ---------------------------------------------------------------------------
# 4. Classifier integration: frozen skip, last_hit_at, conflict
# ---------------------------------------------------------------------------

class TestClassifierFrozenRuleSkip:
    """Frozen rules should be skipped by _try_user_override."""

    def _make_classifier(self):
        from app.services.transaction_classifier import TransactionClassifier
        c = TransactionClassifier.__new__(TransactionClassifier)
        c.db = MagicMock()
        c._user_svc = MagicMock()
        c.ml_classifier = MagicMock()
        c.rule_classifier = MagicMock()
        return c

    def _make_txn(self):
        txn = MagicMock()
        txn.id = 1
        txn.user_id = 1
        txn.description = "BILLA"
        txn.type = MagicMock(value="expense")
        return txn

    def test_frozen_rule_returns_none(self):
        c = self._make_classifier()
        txn = self._make_txn()

        rule = MagicMock()
        rule.frozen = True
        rule.normalized_description = "billa"
        c._user_svc.lookup.return_value = rule

        result = c._try_user_override(txn)
        assert result is None

    def test_non_frozen_rule_returns_result(self):
        c = self._make_classifier()
        txn = self._make_txn()

        rule = MagicMock()
        rule.frozen = False
        rule.category = "groceries"
        rule.confidence = Decimal("1.00")
        rule.hit_count = 3
        rule.normalized_description = "billa"
        rule.rule_type = "strict"
        c._user_svc.lookup.return_value = rule

        result = c._try_user_override(txn)
        assert result is not None
        assert result.category == "groceries"


class TestClassifierRecordsHit:
    """_try_user_override should call record_hit."""

    def test_record_hit_called(self):
        from app.services.transaction_classifier import TransactionClassifier
        c = TransactionClassifier.__new__(TransactionClassifier)
        c.db = MagicMock()
        c._user_svc = MagicMock()
        c.ml_classifier = MagicMock()
        c.rule_classifier = MagicMock()

        txn = MagicMock()
        txn.user_id = 1
        txn.description = "BILLA"
        txn.type = MagicMock(value="expense")

        rule = MagicMock()
        rule.frozen = False
        rule.category = "groceries"
        rule.confidence = Decimal("1.00")
        rule.hit_count = 1
        rule.normalized_description = "billa"
        rule.rule_type = "strict"
        c._user_svc.lookup.return_value = rule

        c._try_user_override(txn)
        c._user_svc.record_hit.assert_called_once_with(rule)


class TestClassifierRecordsConflict:
    """learn_from_correction should record conflict when category differs."""

    def test_conflict_recorded_on_category_mismatch(self):
        from app.services.transaction_classifier import TransactionClassifier
        c = TransactionClassifier.__new__(TransactionClassifier)
        c.db = MagicMock()
        c._user_svc = MagicMock()
        c.ml_classifier = MagicMock()
        c.rule_classifier = MagicMock()

        # Mock classify_transaction
        c.classify_transaction = MagicMock(return_value=MagicMock(
            category="other", confidence=Decimal("0.50"),
        ))

        txn = MagicMock()
        txn.id = 42
        txn.user_id = 1
        txn.description = "BILLA"
        txn.type = MagicMock(value="expense")

        # Existing rule has different category
        existing_rule = MagicMock()
        existing_rule.category = "other"
        c._user_svc.lookup.return_value = existing_rule

        c.learn_from_correction(txn, "groceries", user_id=1)

        c._user_svc.record_conflict.assert_called_once_with(existing_rule)

    def test_no_conflict_when_same_category(self):
        from app.services.transaction_classifier import TransactionClassifier
        c = TransactionClassifier.__new__(TransactionClassifier)
        c.db = MagicMock()
        c._user_svc = MagicMock()
        c.ml_classifier = MagicMock()
        c.rule_classifier = MagicMock()

        c.classify_transaction = MagicMock(return_value=MagicMock(
            category="groceries", confidence=Decimal("0.90"),
        ))

        txn = MagicMock()
        txn.id = 42
        txn.user_id = 1
        txn.description = "BILLA"
        txn.type = MagicMock(value="expense")

        existing_rule = MagicMock()
        existing_rule.category = "groceries"  # same as correction
        c._user_svc.lookup.return_value = existing_rule

        c.learn_from_correction(txn, "groceries", user_id=1)

        c._user_svc.record_conflict.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Model lifecycle fields exist
# ---------------------------------------------------------------------------

class TestModelLifecycleFields:
    """UserClassificationRule should have lifecycle columns."""

    def test_has_last_hit_at(self):
        from app.models.user_classification_rule import UserClassificationRule
        assert hasattr(UserClassificationRule, "last_hit_at")

    def test_has_conflict_count(self):
        from app.models.user_classification_rule import UserClassificationRule
        assert hasattr(UserClassificationRule, "conflict_count")

    def test_has_frozen(self):
        from app.models.user_classification_rule import UserClassificationRule
        assert hasattr(UserClassificationRule, "frozen")

    def test_defaults(self):
        from app.models.user_classification_rule import UserClassificationRule
        rule = UserClassificationRule(
            user_id=1, normalized_description="test", txn_type="expense",
            category="groceries", rule_type="strict",
            conflict_count=0, frozen=False,
        )
        assert rule.conflict_count == 0
        assert rule.frozen is False
        assert rule.last_hit_at is None
