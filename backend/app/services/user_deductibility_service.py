"""Per-user deductibility override service."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping, Optional

from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.core.transaction_enum_coercion import coerce_expense_category
from app.models.user_deductibility_rule import UserDeductibilityRule
from app.services.user_classification_service import normalize_description


def compose_deductibility_rule_description(
    parent_description: Optional[str],
    item_description: Optional[str] = None,
) -> str:
    """Build a stable description token for parent- or item-level overrides."""
    parent = str(parent_description or "").strip()
    item = str(item_description or "").strip()

    if parent and item:
        if item.lower() in parent.lower():
            return parent
        return f"{parent} {item}".strip()
    return parent or item


class UserDeductibilityService:
    """Store and resolve user-confirmed deductible / non-deductible decisions."""

    _ensured_bind_ids: set[int] = set()

    def __init__(self, db: Session):
        self.db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        bind = getattr(self.db, "bind", None)
        if bind is None or not isinstance(bind, (Engine, Connection)):
            return

        bind_id = id(bind)
        if bind_id in self._ensured_bind_ids:
            return

        UserDeductibilityRule.__table__.create(bind=bind, checkfirst=True)
        self._ensured_bind_ids.add(bind_id)

    def lookup(
        self,
        user_id: int,
        description: str,
        expense_category: str,
    ) -> Optional[UserDeductibilityRule]:
        norm = normalize_description(description)
        normalized_category = self._normalize_expense_category(expense_category)
        if not norm or not normalized_category:
            return None

        return (
            self.db.query(UserDeductibilityRule)
            .filter(
                UserDeductibilityRule.user_id == user_id,
                UserDeductibilityRule.normalized_description == norm,
                UserDeductibilityRule.expense_category == normalized_category,
            )
            .first()
        )

    def upsert_rule(
        self,
        user_id: int,
        description: str,
        expense_category: str,
        is_deductible: bool,
        reason: Optional[str] = None,
    ) -> Optional[UserDeductibilityRule]:
        norm = normalize_description(description)
        normalized_category = self._normalize_expense_category(expense_category)
        if not norm or not normalized_category:
            return None

        existing = (
            self.db.query(UserDeductibilityRule)
            .filter(
                UserDeductibilityRule.user_id == user_id,
                UserDeductibilityRule.normalized_description == norm,
                UserDeductibilityRule.expense_category == normalized_category,
            )
            .first()
        )

        if existing:
            existing.is_deductible = bool(is_deductible)
            existing.reason = reason
            existing.original_description = description
            existing.hit_count += 1
            existing.updated_at = datetime.utcnow()
            self.db.flush()
            return existing

        rule = UserDeductibilityRule(
            user_id=user_id,
            normalized_description=norm,
            original_description=description,
            expense_category=normalized_category,
            is_deductible=bool(is_deductible),
            reason=reason,
            hit_count=1,
        )
        self.db.add(rule)
        self.db.flush()
        return rule

    @staticmethod
    def _normalize_expense_category(expense_category: Optional[str]) -> Optional[str]:
        if expense_category is None:
            return None
        normalized = coerce_expense_category(expense_category)
        if normalized is not None:
            return normalized.value

        token = str(expense_category).strip()
        return token.lower() or None

    def record_hit(self, rule: UserDeductibilityRule) -> None:
        rule.last_hit_at = datetime.utcnow()
        self.db.flush()

    def delete_rules_for_description(
        self,
        user_id: int,
        description: str,
        *,
        expense_category: Optional[str] = None,
    ) -> int:
        """Delete deductibility overrides for one normalized description."""
        norm = normalize_description(description)
        if not norm:
            return 0

        query = self.db.query(UserDeductibilityRule).filter(
            UserDeductibilityRule.user_id == user_id,
            UserDeductibilityRule.normalized_description == norm,
        )
        normalized_category = self._normalize_expense_category(expense_category)
        if normalized_category is not None:
            query = query.filter(UserDeductibilityRule.expense_category == normalized_category)

        deleted = query.delete(synchronize_session=False)
        if deleted:
            self.db.flush()
        return deleted

    def delete_rule(self, user_id: int, rule_id: int) -> bool:
        """Delete a specific deductibility override owned by the user."""
        deleted = (
            self.db.query(UserDeductibilityRule)
            .filter(
                UserDeductibilityRule.id == rule_id,
                UserDeductibilityRule.user_id == user_id,
            )
            .delete()
        )
        self.db.flush()
        return deleted > 0

    def list_rules(self, user_id: int) -> list[UserDeductibilityRule]:
        """List all deductibility overrides for a user."""
        return (
            self.db.query(UserDeductibilityRule)
            .filter(UserDeductibilityRule.user_id == user_id)
            .order_by(
                UserDeductibilityRule.hit_count.desc(),
                UserDeductibilityRule.updated_at.desc(),
            )
            .all()
        )

    def learn_from_line_items(
        self,
        *,
        user_id: int,
        parent_description: Optional[str],
        fallback_category: Optional[str],
        line_items: Iterable[Mapping[str, object]],
    ) -> int:
        learned = 0
        seen_keys: set[tuple[str, str]] = set()
        for item in line_items:
            posting_type = getattr(item.get("posting_type"), "value", item.get("posting_type"))
            if posting_type not in (None, "expense"):
                continue

            item_description = str(item.get("description") or "").strip()
            category = str(item.get("category") or fallback_category or "").strip()
            if not item_description or not category:
                continue

            description = compose_deductibility_rule_description(parent_description, item_description)
            if not description:
                continue

            normalized_description = normalize_description(description)
            normalized_category = self._normalize_expense_category(category)
            if not normalized_description or not normalized_category:
                continue

            dedupe_key = (normalized_description, normalized_category)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)

            self.upsert_rule(
                user_id=user_id,
                description=description,
                expense_category=normalized_category,
                is_deductible=bool(item.get("is_deductible")),
                reason=str(item.get("deduction_reason") or "").strip() or None,
            )
            learned += 1

        return learned
