"""
Tests for classification rules API endpoints (GET / and DELETE /{rule_id}).

Tests cover:
1. list_my_rules — returns serialized rules for current user
2. list_my_rules — empty list when no rules
3. delete_my_rule — successful deletion
4. delete_my_rule — 404 when rule not found
5. delete_my_rule — cannot delete another user's rule
6. Serialization correctness (all fields present, types correct)
"""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_rule(**overrides):
    """Create a mock UserClassificationRule with sensible defaults."""
    defaults = {
        "id": 1,
        "normalized_description": "billa wien",
        "original_description": "BILLA Filiale 1234 WIEN",
        "txn_type": "expense",
        "category": "groceries",
        "hit_count": 5,
        "confidence": Decimal("0.95"),
        "rule_type": "strict",
        "frozen": False,
        "conflict_count": 0,
        "last_hit_at": datetime(2026, 3, 1, 12, 0, 0),
        "created_at": datetime(2026, 1, 15, 10, 30, 0),
    }
    defaults.update(overrides)
    rule = MagicMock()
    for k, v in defaults.items():
        setattr(rule, k, v)
    return rule


def _make_mock_deductibility_rule(**overrides):
    """Create a mock UserDeductibilityRule with sensible defaults."""
    defaults = {
        "id": 11,
        "normalized_description": "omv guest shuttle fuel",
        "original_description": "OMV guest shuttle fuel",
        "expense_category": "vehicle",
        "is_deductible": True,
        "reason": "Guest transport for lodging business",
        "hit_count": 3,
        "last_hit_at": datetime(2026, 3, 2, 9, 15, 0),
        "created_at": datetime(2026, 2, 1, 8, 0, 0),
        "updated_at": datetime(2026, 3, 2, 9, 15, 0),
    }
    defaults.update(overrides)
    rule = MagicMock()
    for k, v in defaults.items():
        setattr(rule, k, v)
    return rule


def _make_mock_user(user_id=1, is_admin=False):
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.is_admin = is_admin
    return mock_user


# ---------------------------------------------------------------------------
# 1. list_my_rules
# ---------------------------------------------------------------------------

class TestListMyRules:
    """Tests for GET /classification-rules/"""

    def test_list_returns_rules(self):
        from app.api.v1.endpoints.classification_rules import list_my_rules

        rule1 = _make_mock_rule(id=1, category="groceries", hit_count=5)
        rule2 = _make_mock_rule(
            id=2,
            normalized_description="amazon druckerpatrone",
            original_description="AMAZON EU Druckerpatrone",
            category="office_supplies",
            hit_count=2,
            confidence=Decimal("0.80"),
            rule_type="soft",
            frozen=False,
            conflict_count=1,
            last_hit_at=None,
            created_at=datetime(2026, 2, 20, 8, 0, 0),
        )

        mock_db = MagicMock()
        mock_user = _make_mock_user(user_id=42)

        with patch(
            "app.api.v1.endpoints.classification_rules.UserClassificationService"
        ) as MockSvc:
            MockSvc.return_value.list_rules.return_value = [rule1, rule2]
            result = list_my_rules(current_user=mock_user, db=mock_db)

        assert len(result) == 2
        # First rule
        assert result[0]["id"] == 1
        assert result[0]["category"] == "groceries"
        assert result[0]["hit_count"] == 5
        assert result[0]["confidence"] == 0.95
        assert result[0]["rule_type"] == "strict"
        assert result[0]["frozen"] is False
        assert result[0]["last_hit_at"] == "2026-03-01T12:00:00+00:00"
        assert result[0]["created_at"] == "2026-01-15T10:30:00+00:00"
        # Second rule
        assert result[1]["id"] == 2
        assert result[1]["category"] == "office_supplies"
        assert result[1]["rule_type"] == "soft"
        assert result[1]["last_hit_at"] is None
        assert result[1]["conflict_count"] == 1

        MockSvc.assert_called_once_with(mock_db)
        MockSvc.return_value.list_rules.assert_called_once_with(42)

    def test_list_empty(self):
        from app.api.v1.endpoints.classification_rules import list_my_rules

        mock_db = MagicMock()
        mock_user = _make_mock_user(user_id=99)

        with patch(
            "app.api.v1.endpoints.classification_rules.UserClassificationService"
        ) as MockSvc:
            MockSvc.return_value.list_rules.return_value = []
            result = list_my_rules(current_user=mock_user, db=mock_db)

        assert result == []

    def test_list_serialization_all_fields(self):
        """Ensure all expected fields are present in the response."""
        from app.api.v1.endpoints.classification_rules import list_my_rules

        rule = _make_mock_rule()
        mock_db = MagicMock()
        mock_user = _make_mock_user()

        with patch(
            "app.api.v1.endpoints.classification_rules.UserClassificationService"
        ) as MockSvc:
            MockSvc.return_value.list_rules.return_value = [rule]
            result = list_my_rules(current_user=mock_user, db=mock_db)

        expected_keys = {
            "id", "normalized_description", "original_description",
            "txn_type", "category", "hit_count", "confidence",
            "rule_type", "frozen", "conflict_count", "last_hit_at", "created_at",
        }
        assert set(result[0].keys()) == expected_keys

    def test_confidence_is_float(self):
        """Confidence should be serialized as float, not Decimal."""
        from app.api.v1.endpoints.classification_rules import list_my_rules

        rule = _make_mock_rule(confidence=Decimal("0.85"))
        mock_db = MagicMock()
        mock_user = _make_mock_user()

        with patch(
            "app.api.v1.endpoints.classification_rules.UserClassificationService"
        ) as MockSvc:
            MockSvc.return_value.list_rules.return_value = [rule]
            result = list_my_rules(current_user=mock_user, db=mock_db)

        assert isinstance(result[0]["confidence"], float)
        assert result[0]["confidence"] == 0.85

    def test_list_preserves_auto_rule_type(self):
        from app.api.v1.endpoints.classification_rules import list_my_rules

        rule = _make_mock_rule(rule_type="auto", category="insurance")
        mock_db = MagicMock()
        mock_user = _make_mock_user()

        with patch(
            "app.api.v1.endpoints.classification_rules.UserClassificationService"
        ) as MockSvc:
            MockSvc.return_value.list_rules.return_value = [rule]
            result = list_my_rules(current_user=mock_user, db=mock_db)

        assert result[0]["rule_type"] == "auto"


# ---------------------------------------------------------------------------
# 2. delete_my_rule
# ---------------------------------------------------------------------------

class TestDeleteMyRule:
    """Tests for DELETE /classification-rules/{rule_id}"""

    def test_delete_success(self):
        from app.api.v1.endpoints.classification_rules import delete_my_rule

        mock_db = MagicMock()
        mock_user = _make_mock_user(user_id=42)

        with patch(
            "app.api.v1.endpoints.classification_rules.UserClassificationService"
        ) as MockSvc:
            MockSvc.return_value.delete_rule.return_value = True
            result = delete_my_rule(rule_id=7, current_user=mock_user, db=mock_db)

        assert result == {"deleted": True, "rule_id": 7}
        MockSvc.return_value.delete_rule.assert_called_once_with(42, 7)
        mock_db.commit.assert_called_once()

    def test_delete_not_found(self):
        from fastapi import HTTPException
        from app.api.v1.endpoints.classification_rules import delete_my_rule

        mock_db = MagicMock()
        mock_user = _make_mock_user(user_id=42)

        with patch(
            "app.api.v1.endpoints.classification_rules.UserClassificationService"
        ) as MockSvc:
            MockSvc.return_value.delete_rule.return_value = False
            with pytest.raises(HTTPException) as exc_info:
                delete_my_rule(rule_id=999, current_user=mock_user, db=mock_db)

        assert exc_info.value.status_code == 404
        assert "Rule not found" in str(exc_info.value.detail)
        mock_db.commit.assert_not_called()

    def test_delete_scoped_to_user(self):
        """delete_rule is called with the current user's ID, not the rule owner."""
        from app.api.v1.endpoints.classification_rules import delete_my_rule

        mock_db = MagicMock()
        mock_user = _make_mock_user(user_id=77)

        with patch(
            "app.api.v1.endpoints.classification_rules.UserClassificationService"
        ) as MockSvc:
            MockSvc.return_value.delete_rule.return_value = True
            delete_my_rule(rule_id=5, current_user=mock_user, db=mock_db)

        # Verify user_id=77 is passed, ensuring user can only delete own rules
        MockSvc.return_value.delete_rule.assert_called_once_with(77, 5)


# ---------------------------------------------------------------------------
# 2b. deductibility memory endpoints
# ---------------------------------------------------------------------------

class TestListMyDeductibilityRules:
    """Tests for GET /classification-rules/deductibility"""

    def test_list_returns_deductibility_rules(self):
        from app.api.v1.endpoints.classification_rules import list_my_deductibility_rules

        rule = _make_mock_deductibility_rule()
        mock_db = MagicMock()
        mock_user = _make_mock_user(user_id=42)

        with patch(
            "app.api.v1.endpoints.classification_rules.UserDeductibilityService"
        ) as MockSvc:
            MockSvc.return_value.list_rules.return_value = [rule]
            result = list_my_deductibility_rules(current_user=mock_user, db=mock_db)

        assert result == [{
            "id": 11,
            "normalized_description": "omv guest shuttle fuel",
            "original_description": "OMV guest shuttle fuel",
            "expense_category": "vehicle",
            "is_deductible": True,
            "reason": "Guest transport for lodging business",
            "hit_count": 3,
            "last_hit_at": "2026-03-02T09:15:00+00:00",
            "created_at": "2026-02-01T08:00:00+00:00",
            "updated_at": "2026-03-02T09:15:00+00:00",
        }]
        MockSvc.return_value.list_rules.assert_called_once_with(42)

    def test_list_empty(self):
        from app.api.v1.endpoints.classification_rules import list_my_deductibility_rules

        mock_db = MagicMock()
        mock_user = _make_mock_user(user_id=9)

        with patch(
            "app.api.v1.endpoints.classification_rules.UserDeductibilityService"
        ) as MockSvc:
            MockSvc.return_value.list_rules.return_value = []
            result = list_my_deductibility_rules(current_user=mock_user, db=mock_db)

        assert result == []


class TestDeleteMyDeductibilityRule:
    """Tests for DELETE /classification-rules/deductibility/{rule_id}"""

    def test_delete_success(self):
        from app.api.v1.endpoints.classification_rules import delete_my_deductibility_rule

        mock_db = MagicMock()
        mock_user = _make_mock_user(user_id=42)

        with patch(
            "app.api.v1.endpoints.classification_rules.UserDeductibilityService"
        ) as MockSvc:
            MockSvc.return_value.delete_rule.return_value = True
            result = delete_my_deductibility_rule(rule_id=11, current_user=mock_user, db=mock_db)

        assert result == {"deleted": True, "rule_id": 11}
        MockSvc.return_value.delete_rule.assert_called_once_with(42, 11)
        mock_db.commit.assert_called_once()

    def test_delete_not_found(self):
        from fastapi import HTTPException
        from app.api.v1.endpoints.classification_rules import delete_my_deductibility_rule

        mock_db = MagicMock()
        mock_user = _make_mock_user(user_id=42)

        with patch(
            "app.api.v1.endpoints.classification_rules.UserDeductibilityService"
        ) as MockSvc:
            MockSvc.return_value.delete_rule.return_value = False
            with pytest.raises(HTTPException) as exc_info:
                delete_my_deductibility_rule(rule_id=404, current_user=mock_user, db=mock_db)

        assert exc_info.value.status_code == 404
        assert "Rule not found" in str(exc_info.value.detail)
        mock_db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# 3. UserClassificationService.list_rules / delete_rule unit tests
# ---------------------------------------------------------------------------

class TestUserClassificationServiceListDelete:
    """Direct service-level tests for list_rules and delete_rule."""

    def test_list_rules_queries_by_user(self):
        from app.services.user_classification_service import UserClassificationService

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        svc = UserClassificationService(mock_db)
        result = svc.list_rules(user_id=42)

        assert result == []
        mock_db.query.assert_called_once()

    def test_delete_rule_returns_true_on_success(self):
        from app.services.user_classification_service import UserClassificationService

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 1  # 1 row deleted

        svc = UserClassificationService(mock_db)
        result = svc.delete_rule(user_id=42, rule_id=7)

        assert result is True

    def test_delete_rule_returns_false_when_not_found(self):
        from app.services.user_classification_service import UserClassificationService

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 0  # 0 rows deleted

        svc = UserClassificationService(mock_db)
        result = svc.delete_rule(user_id=42, rule_id=999)

        assert result is False
