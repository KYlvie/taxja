"""Shared rule resolution for OCR and transaction workflows.

First phase scope:
- classification rules apply to OCR receipt/invoice, bank import, and manual flows
- deductibility rules apply to OCR receipt/invoice and manual flows
- auto rules remain bank-import only
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Mapping, Optional

from sqlalchemy.orm import Session

from app.services.user_classification_service import UserClassificationService
from app.services.user_deductibility_service import (
    UserDeductibilityService,
    compose_deductibility_rule_description,
)


def build_ocr_parent_description(
    *,
    merchant: Optional[str],
    ocr_description: Optional[str],
    fallback_description: Optional[str],
) -> str:
    """Build the stable parent description used by receipt OCR rule learning."""
    merchant_token = str(merchant or "").strip()
    description_token = str(ocr_description or "").strip()
    fallback_token = str(fallback_description or "").strip()

    if merchant_token and description_token:
        return f"{merchant_token}: {description_token}"
    if merchant_token:
        return merchant_token
    if description_token:
        return description_token
    return fallback_token


def build_candidate_descriptions(
    *,
    canonical_description: str,
    line_items: Optional[Iterable[Mapping[str, object]]] = None,
) -> list[str]:
    """Build parent- and item-level description candidates for rule lookup."""
    candidates: list[str] = []

    def _append(value: Optional[str]) -> None:
        token = str(value or "").strip()
        if token and token not in candidates:
            candidates.append(token)

    _append(canonical_description)

    for item in line_items or []:
        item_description = str(
            item.get("description") or item.get("name") or ""
        ).strip()
        if not item_description:
            continue
        _append(
            compose_deductibility_rule_description(
                canonical_description,
                item_description,
            )
        )

    return candidates


@dataclass
class ResolvedRuleSet:
    canonical_description: str = ""
    candidate_descriptions: list[str] = field(default_factory=list)
    resolved_category: Optional[str] = None
    resolved_txn_type: Optional[str] = None
    classification_rule_id: Optional[int] = None
    classification_confidence: Optional[Decimal] = None
    classification_method: Optional[str] = None
    resolved_is_deductible: Optional[bool] = None
    resolved_deduction_reason: Optional[str] = None
    deductibility_rule_id: Optional[int] = None
    applied_sources: list[str] = field(default_factory=list)


class TransactionRuleResolver:
    """Resolve classification and deductibility rules using canonical descriptions."""

    _ALLOWED_RULE_TYPES = {
        "ocr_receipt": ("strict", "soft"),
        "manual_transaction": ("strict", "soft"),
        "bank_import": ("strict", "soft", "auto"),
    }

    def __init__(self, db: Session):
        self.db = db
        self.classification_service = UserClassificationService(db)
        self.deductibility_service = UserDeductibilityService(db)

    def resolve(
        self,
        *,
        user_id: int,
        context: str,
        txn_type: str,
        canonical_description: str,
        line_items: Optional[Iterable[Mapping[str, object]]] = None,
        ocr_category: Optional[str] = None,
    ) -> ResolvedRuleSet:
        candidate_descriptions = build_candidate_descriptions(
            canonical_description=canonical_description,
            line_items=line_items,
        )
        resolved = ResolvedRuleSet(
            canonical_description=canonical_description,
            candidate_descriptions=candidate_descriptions,
        )

        classification_rule = self._resolve_classification_rule(
            user_id=user_id,
            txn_type=txn_type,
            context=context,
            candidate_descriptions=candidate_descriptions,
        )
        if classification_rule is not None:
            self.classification_service.record_hit(classification_rule)
            resolved.resolved_category = classification_rule.category
            resolved.resolved_txn_type = classification_rule.txn_type
            resolved.classification_rule_id = classification_rule.id
            resolved.classification_confidence = Decimal(
                str(getattr(classification_rule, "confidence", Decimal("1.00")))
            )
            rule_type = getattr(classification_rule, "rule_type", "strict")
            resolved.classification_method = (
                "user_rule_soft" if rule_type == "soft" else "user_rule"
            )
            resolved.applied_sources.append(f"classification:{rule_type}")
        else:
            resolved.resolved_category = ocr_category

        target_category = resolved.resolved_category or ocr_category
        if txn_type == "expense" and target_category:
            deductibility_rule = self._resolve_deductibility_rule(
                user_id=user_id,
                expense_category=target_category,
                candidate_descriptions=candidate_descriptions,
            )
            if deductibility_rule is not None:
                self.deductibility_service.record_hit(deductibility_rule)
                resolved.resolved_is_deductible = bool(
                    getattr(deductibility_rule, "is_deductible", False)
                )
                resolved.resolved_deduction_reason = (
                    getattr(deductibility_rule, "reason", None)
                    or "Learned from your previous correction"
                )
                resolved.deductibility_rule_id = deductibility_rule.id
                resolved.applied_sources.append("deductibility:user_rule")

        return resolved

    def _resolve_classification_rule(
        self,
        *,
        user_id: int,
        txn_type: str,
        context: str,
        candidate_descriptions: list[str],
    ):
        if not candidate_descriptions:
            return None

        allowed_rule_types = self._ALLOWED_RULE_TYPES.get(
            context,
            ("strict", "soft"),
        )

        # Try current txn_type first, then the opposite direction
        # This allows rules learned as "income" to override an "expense" default
        txn_types_to_try = [txn_type]
        opposite = "income" if txn_type == "expense" else "expense"
        txn_types_to_try.append(opposite)

        for try_type in txn_types_to_try:
            parent_rule = self.classification_service.lookup(
                user_id=user_id,
                description=candidate_descriptions[0],
                txn_type=try_type,
                allowed_rule_types=allowed_rule_types,
                include_frozen=False,
            )
            if parent_rule is not None:
                return parent_rule

            item_rules = []
            for description in candidate_descriptions[1:]:
                rule = self.classification_service.lookup(
                    user_id=user_id,
                    description=description,
                    txn_type=try_type,
                    allowed_rule_types=allowed_rule_types,
                    include_frozen=False,
                )
                if rule is not None:
                    item_rules.append(rule)

            if not item_rules:
                continue

            categories = {rule.category for rule in item_rules if getattr(rule, "category", None)}
            if len(categories) != 1:
                continue

            return self._pick_best_rule(item_rules)

        return None

    def _resolve_deductibility_rule(
        self,
        *,
        user_id: int,
        expense_category: str,
        candidate_descriptions: list[str],
    ):
        if not candidate_descriptions:
            return None

        parent_rule = self.deductibility_service.lookup(
            user_id=user_id,
            description=candidate_descriptions[0],
            expense_category=expense_category,
        )
        if parent_rule is not None:
            return parent_rule

        item_rules = []
        for description in candidate_descriptions[1:]:
            rule = self.deductibility_service.lookup(
                user_id=user_id,
                description=description,
                expense_category=expense_category,
            )
            if rule is not None:
                item_rules.append(rule)

        if not item_rules:
            return None

        decisions = {bool(getattr(rule, "is_deductible", False)) for rule in item_rules}
        if len(decisions) != 1:
            return None

        return self._pick_best_rule(item_rules)

    @staticmethod
    def _pick_best_rule(rules: Iterable[object]):
        def _score(rule: object) -> tuple[Decimal, int, int]:
            confidence = Decimal(str(getattr(rule, "confidence", Decimal("1.00"))))
            hit_count = int(getattr(rule, "hit_count", 0) or 0)
            rule_id = int(getattr(rule, "id", 0) or 0)
            return confidence, hit_count, rule_id

        return max(rules, key=_score)
