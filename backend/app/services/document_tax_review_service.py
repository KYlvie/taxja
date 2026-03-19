"""Helpers for backfilling line-item tax judgments on receipt documents."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.document import Document, DocumentType
from app.models.user import User
from app.services.deductibility_checker import DeductibilityChecker
from app.services.rule_based_classifier import RuleBasedClassifier

RECEIPT_TYPES = {DocumentType.RECEIPT, DocumentType.INVOICE}
_CATEGORY_FALLBACKS = {
    "property_management_fees": "professional_services",
    "property_insurance": "insurance",
    "depreciation_afa": "depreciation",
    "other_expense": "other",
}


def backfill_document_tax_review(
    db: Session,
    document: Document,
    user: User,
) -> bool:
    """Populate missing line-item deductibility judgments on legacy OCR results."""
    if document.document_type not in RECEIPT_TYPES:
        return False
    if not isinstance(document.ocr_result, dict):
        return False

    ocr_result = deepcopy(document.ocr_result)
    receipt_targets = _get_receipt_targets(ocr_result)
    if not receipt_targets:
        return False

    changed = False
    primary_analysis: Optional[Dict[str, Any]] = None

    for index, receipt in enumerate(receipt_targets):
        updated = _backfill_receipt(receipt, user)
        if updated is not None:
            changed = True
            if index == 0:
                primary_analysis = updated

    if primary_analysis is not None:
        ocr_result["tax_analysis"] = primary_analysis

    if not changed:
        return False

    document.ocr_result = ocr_result
    flag_modified(document, "ocr_result")
    db.add(document)
    db.commit()
    db.refresh(document)
    return True


def _get_receipt_targets(ocr_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    multiple_receipts = ocr_result.get("multiple_receipts")
    if isinstance(multiple_receipts, list) and multiple_receipts:
        return [receipt for receipt in multiple_receipts if isinstance(receipt, dict)]

    targets: List[Dict[str, Any]] = []
    if _get_receipt_items(ocr_result):
        targets.append(ocr_result)

    additional_receipts = ocr_result.get("_additional_receipts")
    if isinstance(additional_receipts, list):
        targets.extend(receipt for receipt in additional_receipts if isinstance(receipt, dict))

    return targets


def _get_receipt_items(receipt: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_items = receipt.get("line_items")
    if not isinstance(raw_items, list):
        raw_items = receipt.get("items")
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict)]


def _backfill_receipt(receipt: Dict[str, Any], user: User) -> Optional[Dict[str, Any]]:
    items = _get_receipt_items(receipt)
    if not items:
        return None

    merchant = str(receipt.get("merchant") or receipt.get("supplier") or "").strip()
    classifier = RuleBasedClassifier()
    checker = DeductibilityChecker()
    business_type = getattr(user, "business_type", None)
    business_industry = getattr(user, "business_industry", None)
    user_type = (
        user.user_type.value
        if hasattr(user.user_type, "value")
        else str(user.user_type or "employee")
    )

    updated_items: List[Dict[str, Any]] = []
    changed = False

    for item in items:
        updated_item = dict(item)
        description = str(
            updated_item.get("description")
            or updated_item.get("name")
            or updated_item.get("title")
            or ""
        ).strip()
        amount = _get_item_amount(updated_item)

        needs_category = not updated_item.get("category")
        needs_decision = not isinstance(updated_item.get("is_deductible"), bool)
        needs_reason = not str(updated_item.get("deduction_reason") or "").strip()

        if description and (needs_category or needs_decision or needs_reason):
            category = _resolve_item_category(classifier, description, merchant)
            if needs_category and category:
                updated_item["category"] = category
                changed = True

            result = checker.check(
                expense_category=category or "other",
                user_type=user_type,
                ocr_data={
                    "merchant": merchant,
                    "amount": amount,
                    "line_items": [updated_item],
                },
                description=f"{merchant} {description}".strip(),
                business_type=business_type,
                business_industry=business_industry,
            )

            if needs_decision:
                updated_item["is_deductible"] = result.is_deductible
                changed = True
            if needs_reason:
                updated_item["deduction_reason"] = result.reason
                changed = True
            updated_item["requires_review"] = result.requires_review

        if not updated_item.get("description") and updated_item.get("name"):
            updated_item["description"] = updated_item["name"]
            changed = True

        updated_items.append(updated_item)

    if changed:
        receipt["line_items"] = updated_items
        receipt["items"] = updated_items

    return _build_tax_analysis(updated_items)


def _resolve_item_category(
    classifier: RuleBasedClassifier,
    description: str,
    merchant: str,
) -> str:
    synthetic = SimpleNamespace(
        description=f"{merchant} {description}".strip(),
        type="expense",
    )
    result = classifier.classify(synthetic)
    category = result.category or "other"
    return _CATEGORY_FALLBACKS.get(category, category)


def _get_item_amount(item: Dict[str, Any]) -> float:
    for key in ("total", "total_price", "amount", "price", "unit_price"):
        value = item.get(key)
        if value in (None, ""):
            continue
        try:
            return float(Decimal(str(value)).quantize(Decimal("0.01")))
        except (InvalidOperation, ValueError):
            continue
    return 0.0


def _build_tax_analysis(items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    normalized_items = []
    deductible_amount = Decimal("0")
    non_deductible_amount = Decimal("0")

    for item in items:
        amount = Decimal(str(_get_item_amount(item)))
        is_deductible = item.get("is_deductible") is True
        normalized = {
            "description": item.get("description") or item.get("name") or "",
            "amount": float(amount),
            "category": item.get("category"),
            "is_deductible": is_deductible,
            "deduction_reason": item.get("deduction_reason") or "",
        }
        normalized_items.append(normalized)
        if is_deductible:
            deductible_amount += amount
        else:
            non_deductible_amount += amount

    return {
        "items": normalized_items,
        "deductible_amount": float(deductible_amount),
        "non_deductible_amount": float(non_deductible_amount),
        "total_deductible": float(deductible_amount),
        "total_non_deductible": float(non_deductible_amount),
        "is_split": deductible_amount > 0 and non_deductible_amount > 0,
    }
