"""Service for creating transaction suggestions from OCR data"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
import logging

from app.core.transaction_enum_coercion import (
    coerce_expense_category,
    coerce_income_category,
    coerce_transaction_type,
)
from app.models.document import Document, DocumentType
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.transaction_line_item import (
    LineItemAllocationSource,
    TransactionLineItem,
)
from app.services.posting_line_utils import (
    build_mirror_line_item_payload,
    default_posting_type_for_transaction_type,
    normalize_line_item_payloads,
    replace_transaction_line_items,
)
from app.services.contract_role_service import (
    ContractRoleService,
    TransactionDirectionResolution,
    get_sensitive_document_mode,
    load_sensitive_user_context,
)
from app.services.duplicate_detector import DuplicateDetector
from app.services.field_normalization import (
    normalize_amount,
    normalize_boolean_flag,
    normalize_currency,
    normalize_date,
    normalize_quantity,
    normalize_semantic_flags,
    normalize_vat_rate,
)
from app.services.transaction_classifier import TransactionClassifier
from app.services.deductibility_checker import DeductibilityChecker
from app.services.transaction_rule_resolver import (
    TransactionRuleResolver,
    build_ocr_parent_description,
)
from app.services.final_transaction_type_service import (
    materialize_final_transaction_type,
)

logger = logging.getLogger(__name__)


@dataclass
class OCRTransactionCreationResult:
    """Result of OCR transaction creation, including deduplication outcome."""

    transaction: Transaction
    created: bool
    duplicate_of_id: Optional[int] = None
    duplicate_confidence: Optional[float] = None


class OCRTransactionService:
    """Service for creating transaction suggestions from OCR results"""

    def __init__(self, db: Session):
        self.db = db
        self.classifier = TransactionClassifier(db=db)
        self.deductibility_checker = DeductibilityChecker(db=db)
        self.duplicate_detector = DuplicateDetector(db)
        self.rule_resolver = TransactionRuleResolver(db=db)

    @staticmethod
    def _direction_metadata_payload(
        resolution: Optional[TransactionDirectionResolution],
    ) -> Dict[str, Any]:
        if not resolution:
            return {}
        return {
            "document_transaction_direction": resolution.candidate,
            "document_transaction_direction_source": resolution.source,
            "document_transaction_direction_confidence": resolution.confidence,
            "transaction_direction_resolution": resolution.to_payload(),
            "commercial_document_semantics": resolution.semantics,
            "is_reversal": resolution.is_reversal,
        }

    def _persist_direction_metadata(
        self,
        document: Document,
        resolution: Optional[TransactionDirectionResolution],
    ) -> None:
        if not resolution or not isinstance(document.ocr_result, dict):
            return
        metadata = self._direction_metadata_payload(resolution)
        updated = dict(document.ocr_result)
        changed = False
        for key, value in metadata.items():
            if updated.get(key) != value:
                updated[key] = value
                changed = True
        if not changed:
            return
        document.ocr_result = updated
        flag_modified(document, "ocr_result")
        self.db.flush()

    def _resolve_direction(
        self,
        document: Document,
        user_id: int,
    ) -> Optional[TransactionDirectionResolution]:
        if not isinstance(document.ocr_result, dict):
            return None
        user = load_sensitive_user_context(self.db, user_id)
        if not user:
            return None
        service = ContractRoleService(language=getattr(user, "language", None))
        resolution = service.resolve_transaction_direction(
            user,
            document.document_type,
            document.ocr_result,
            raw_text=document.raw_text,
        )
        self._persist_direction_metadata(document, resolution)
        return resolution

    def _enforce_direction_gate(
        self,
        suggestion: Dict[str, Any],
        user_id: int,
    ) -> Optional[TransactionDirectionResolution]:
        document_id = suggestion.get("document_id")
        if not document_id:
            return None
        document = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.user_id == user_id)
            .first()
        )
        if not document:
            return None
        resolution = self._resolve_direction(document, user_id)
        if (
            resolution
            and get_sensitive_document_mode() == "strict"
            and resolution.gate_enabled
            and resolution.strict_would_block
        ):
            raise ValueError(
                "Automatic transaction creation is blocked until you confirm the document direction."
            )
        return resolution

    def _annotate_suggestion_with_direction(
        self,
        suggestion: Dict[str, Any],
        resolution: Optional[TransactionDirectionResolution],
    ) -> Dict[str, Any]:
        if not resolution:
            return suggestion
        suggestion.update(self._direction_metadata_payload(resolution))
        return suggestion

    def create_transaction_suggestion(
        self, document_id: int, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Create a transaction suggestion from OCR data.
        Returns the first (or only) suggestion. For split receipts, use
        create_split_suggestions() instead.
        """
        suggestions = self.create_split_suggestions(document_id, user_id)
        if not suggestions:
            return None
        return suggestions[0]

    def create_split_suggestions(
        self, document_id: int, user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Create transaction suggestions from OCR data. If the receipt contains
        a mix of deductible and non-deductible items (e.g. office supplies +
        personal groceries on one Billa receipt), AI splits it into two
        separate suggestions with correct amounts.

        Returns:
            List of 1-2 suggestion dicts, or empty list if not enough data.
        """
        document = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.user_id == user_id)
            .first()
        )

        if not document or not document.ocr_result:
            logger.warning(f"Document {document_id} not found or has no OCR results")
            return []

        ocr_data = document.ocr_result
        direction_resolution = self._resolve_direction(document, user_id)
        if (
            direction_resolution
            and get_sensitive_document_mode() == "strict"
            and direction_resolution.gate_enabled
            and direction_resolution.strict_would_block
        ):
            logger.info(
                "Sensitive direction gate blocked automatic suggestion creation for document %s",
                document_id,
            )
            return []
        transaction_data = self._extract_transaction_data(document, ocr_data)

        if not transaction_data:
            logger.warning(f"Could not extract transaction data from document {document_id}")
            return []

        classification = self._classify_from_ocr(
            document,
            transaction_data,
            user_id,
            direction_resolution=direction_resolution,
        )

        # Check if this is a NEEDS_AI category that might benefit from split analysis
        doc_type = str(document.document_type.value) if hasattr(document.document_type, 'value') else str(document.document_type)
        line_items = ocr_data.get("line_items") or ocr_data.get("items") or []

        if (
            doc_type in [DocumentType.RECEIPT.value, DocumentType.INVOICE.value]
            and classification["transaction_type"] == TransactionType.EXPENSE.value
            and line_items
            and len(line_items) >= 2
        ):
            user = load_sensitive_user_context(self.db, user_id)
            if user:
                user_type_val = user.user_type.value if hasattr(user.user_type, 'value') else str(user.user_type or "employee")
                # Only attempt split for business user types
                if user_type_val in ("self_employed", "mixed", "gmbh"):
                    split = self.deductibility_checker.ai_split_analyze(
                        user_type_val, ocr_data, transaction_data.get("description", "")
                    )
                    if split and split.get("has_split"):
                        return self._build_split_suggestions(
                            document,
                            transaction_data,
                            classification,
                            split,
                            ocr_data,
                            direction_resolution=direction_resolution,
                        )

        # No split needed — return single suggestion
        suggestion = self._build_single_suggestion(
            document,
            transaction_data,
            classification,
            ocr_data,
            direction_resolution=direction_resolution,
        )
        return [suggestion]

    def _build_single_suggestion(
        self,
        document,
        transaction_data,
        classification,
        ocr_data,
        *,
        direction_resolution: Optional[TransactionDirectionResolution] = None,
    ) -> Dict[str, Any]:
        """Build a single transaction suggestion dict."""
        suggestion = {
            "document_id": document.id,
            "document_type": str(document.document_type.value) if hasattr(document.document_type, 'value') else str(document.document_type),
            "transaction_type": classification["transaction_type"],
            "amount": str(transaction_data["amount"]),
            "date": transaction_data["date"].isoformat() if transaction_data["date"] and hasattr(transaction_data["date"], 'isoformat') else str(transaction_data["date"]) if transaction_data["date"] else None,
            "description": transaction_data["description"],
            "category": classification["category"],
            "is_deductible": classification["is_deductible"],
            "deduction_reason": classification["deduction_reason"],
            "confidence": float(classification["confidence"]) if hasattr(classification["confidence"], '__float__') else classification["confidence"],
            "needs_review": (float(classification["confidence"]) < 0.7 if classification["confidence"] else True) or classification.get("requires_review", False),
            "classification_method": classification.get("classification_method"),
            "classification_rule_id": classification.get("classification_rule_id"),
            "deductibility_rule_id": classification.get("deductibility_rule_id"),
            "applied_rule_sources": classification.get("applied_rule_sources", []),
            "canonical_description": classification.get("canonical_description"),
            "extracted_fields": {k: (float(v) if isinstance(v, Decimal) else v.isoformat() if isinstance(v, (datetime,)) else v) for k, v in ocr_data.items()} if ocr_data else {},
        }
        return self._annotate_suggestion_with_direction(suggestion, direction_resolution)

    def _build_line_items_from_split(
        self,
        ocr_items: List[Dict[str, Any]],
        split: Dict[str, Any],
        deductible_category: str,
        deductible_reason: str,
        non_deductible_reason: str,
    ) -> List[Dict[str, Any]]:
        """Map OCR receipt items into canonical deductible/private-use line items."""
        if not ocr_items:
            return []

        deductible_tokens = {
            token.strip().lower()
            for token in str(split.get("deductible_items") or "").split(",")
            if token and token.strip()
        }
        non_deductible_tokens = {
            token.strip().lower()
            for token in str(split.get("non_deductible_items") or "").split(",")
            if token and token.strip()
        }

        line_items: List[Dict[str, Any]] = []
        for idx, item in enumerate(ocr_items):
            description = (item.get("description") or item.get("name") or "").strip()
            if not description:
                continue

            raw_amount = (
                item.get("amount")
                or item.get("total_price")
                or item.get("total")
                or item.get("price")
            )
            if raw_amount in (None, ""):
                continue

            desc_lower = description.lower()
            is_deductible = any(token in desc_lower for token in deductible_tokens)
            is_non_deductible = any(token in desc_lower for token in non_deductible_tokens)

            if is_deductible and not is_non_deductible:
                posting_type = "expense"
                category = deductible_category
                deduction_reason = deductible_reason
                deductible_flag = True
            else:
                posting_type = "private_use"
                category = "groceries"
                deduction_reason = non_deductible_reason
                deductible_flag = False

            line_items.append(
                {
                    "description": description[:500],
                    "amount": str(raw_amount),
                    "quantity": item.get("quantity", 1) or 1,
                    "posting_type": posting_type,
                    "allocation_source": "ocr_split",
                    "category": category,
                    "is_deductible": deductible_flag,
                    "deduction_reason": deduction_reason[:500] if deduction_reason else None,
                    "vat_rate": item.get("vat_rate"),
                    "vat_amount": item.get("vat_amount"),
                    "vat_recoverable_amount": "0.00",
                    "sort_order": idx,
                }
            )

        return line_items

    def _build_split_suggestions(
        self,
        document,
        transaction_data,
        classification,
        split,
        ocr_data,
        *,
        direction_resolution: Optional[TransactionDirectionResolution] = None,
    ) -> List[Dict[str, Any]]:
        """Build two suggestions from AI split analysis."""
        merchant = ocr_data.get("merchant", "")
        base_date = transaction_data["date"]
        date_str = (
            base_date.isoformat()
            if base_date and hasattr(base_date, "isoformat")
            else str(base_date) if base_date else None
        )
        total = transaction_data["amount"]
        deduct_amt = normalize_amount(split.get("deductible_amount"))
        non_deduct_amt = normalize_amount(split.get("non_deductible_amount"))
        if deduct_amt is None or non_deduct_amt is None:
            return [
                self._build_single_suggestion(
                    document,
                    transaction_data,
                    classification,
                    ocr_data,
                    direction_resolution=direction_resolution,
                )
            ]
        split_total = deduct_amt + non_deduct_amt
        diff = abs(split_total - total)

        if diff > Decimal("2.0"):
            logger.warning(
                "Split amounts (%.2f + %.2f = %.2f) don't match total %.2f (diff=%.2f), skipping split",
                deduct_amt, non_deduct_amt, split_total, total, diff,
            )
            return [
                self._build_single_suggestion(
                    document,
                    transaction_data,
                    classification,
                    ocr_data,
                    direction_resolution=direction_resolution,
                )
            ]

        if diff > Decimal("0.01"):
            if deduct_amt >= non_deduct_amt:
                deduct_amt = total - non_deduct_amt
            else:
                non_deduct_amt = total - deduct_amt

        deduct_reason = split.get("deductible_reason", "Betriebsausgabe")
        non_deduct_reason = split.get("non_deductible_reason", "Private Lebensfuehrung")
        tax_tip = split.get("tax_tip", "")
        merged_deduct_reason = (
            f"{deduct_reason} | {tax_tip}".strip(" |") if tax_tip else deduct_reason
        )[:500]

        line_items = self._build_line_items_from_split(
            ocr_data.get("line_items") or ocr_data.get("items") or [],
            split,
            classification.get("category", "other"),
            merged_deduct_reason,
            non_deduct_reason[:500],
        )
        if not line_items:
            if deduct_amt > 0:
                deduct_items = split.get("deductible_items", "")
                line_items.append(
                    {
                        "description": (
                            f"{merchant}: {deduct_items}"
                            if deduct_items
                            else f"{merchant} (Betriebsausgabe)"
                        )[:500],
                        "amount": str(deduct_amt),
                        "quantity": 1,
                        "posting_type": "expense",
                        "allocation_source": "ocr_split",
                        "category": classification.get("category", "other"),
                        "is_deductible": True,
                        "deduction_reason": merged_deduct_reason,
                        "sort_order": len(line_items),
                    }
                )
            if non_deduct_amt > 0:
                non_deduct_items = split.get("non_deductible_items", "")
                line_items.append(
                    {
                        "description": (
                            f"{merchant}: {non_deduct_items}"
                            if non_deduct_items
                            else f"{merchant} (Privat)"
                        )[:500],
                        "amount": str(non_deduct_amt),
                        "quantity": 1,
                        "posting_type": "private_use",
                        "allocation_source": "ocr_split",
                        "category": "groceries",
                        "is_deductible": False,
                        "deduction_reason": non_deduct_reason[:500],
                        "sort_order": len(line_items),
                    }
                )

        if line_items:
            suggestion = {
                "document_id": document.id,
                "document_type": str(document.document_type.value) if hasattr(document.document_type, "value") else str(document.document_type),
                "transaction_type": TransactionType.EXPENSE.value,
                "amount": str(total),
                "date": date_str,
                "description": transaction_data["description"],
                "category": classification.get("category", "other"),
                "is_deductible": True,
                "deduction_reason": merged_deduct_reason,
                "confidence": 0.85,
                "needs_review": False,
                "line_items": line_items,
                "classification_method": classification.get("classification_method"),
                "classification_rule_id": classification.get("classification_rule_id"),
                "deductibility_rule_id": classification.get("deductibility_rule_id"),
                "applied_rule_sources": classification.get("applied_rule_sources", []),
                "canonical_description": classification.get("canonical_description"),
                "extracted_fields": {},
            }
            return [
                self._annotate_suggestion_with_direction(
                    suggestion,
                    direction_resolution,
                )
            ]

        suggestions = []
        merchant = ocr_data.get("merchant", "")
        base_date = transaction_data["date"]
        date_str = base_date.isoformat() if base_date and hasattr(base_date, 'isoformat') else str(base_date) if base_date else None

        deduct_amt = normalize_amount(split.get("deductible_amount"))
        non_deduct_amt = normalize_amount(split.get("non_deductible_amount"))
        if deduct_amt is None or non_deduct_amt is None:
            return [
                self._build_single_suggestion(
                    document,
                    transaction_data,
                    classification,
                    ocr_data,
                    direction_resolution=direction_resolution,
                )
            ]

        # Sanity check: amounts should roughly add up to total
        total = transaction_data["amount"]
        split_total = deduct_amt + non_deduct_amt
        diff = abs(split_total - total)
        if diff > Decimal("2.0"):
            # AI amounts way off — fall back to single suggestion
            logger.warning(
                "Split amounts (%.2f + %.2f = %.2f) don't match total %.2f (diff=%.2f), skipping split",
                deduct_amt, non_deduct_amt, split_total, total, diff,
            )
            return [
                self._build_single_suggestion(
                    document,
                    transaction_data,
                    classification,
                    ocr_data,
                    direction_resolution=direction_resolution,
                )
            ]

        # Auto-correct small rounding differences by adjusting the larger portion
        if diff > Decimal("0.01"):
            if deduct_amt >= non_deduct_amt:
                deduct_amt = total - non_deduct_amt
            else:
                non_deduct_amt = total - deduct_amt
            logger.info("Adjusted split amounts to match total: deductible=%.2f, non-deductible=%.2f", deduct_amt, non_deduct_amt)

        deduct_reason = split.get("deductible_reason", "Betriebsausgabe")
        non_deduct_reason = split.get("non_deductible_reason", "Private Lebensführung")
        tax_tip = split.get("tax_tip", "")

        # 1) Deductible portion
        if deduct_amt > 0:
            deduct_items = split.get("deductible_items", "")
            desc = f"{merchant}: {deduct_items}" if deduct_items else f"{merchant} (Betriebsausgabe)"
            reason = deduct_reason
            if tax_tip:
                reason = f"{deduct_reason} | {tax_tip}"
            suggestions.append({
                "document_id": document.id,
                "document_type": str(document.document_type.value) if hasattr(document.document_type, 'value') else str(document.document_type),
                "transaction_type": TransactionType.EXPENSE.value,
                "amount": str(deduct_amt),
                "date": date_str,
                "description": desc[:500],
                "category": classification.get("category", "other"),
                "is_deductible": True,
                "deduction_reason": reason[:500],
                "confidence": 0.85,
                "needs_review": False,
                "classification_method": classification.get("classification_method"),
                "classification_rule_id": classification.get("classification_rule_id"),
                "deductibility_rule_id": classification.get("deductibility_rule_id"),
                "applied_rule_sources": classification.get("applied_rule_sources", []),
                "canonical_description": classification.get("canonical_description"),
                "extracted_fields": {},
            })

        # 2) Non-deductible portion
        if non_deduct_amt > 0:
            non_deduct_items = split.get("non_deductible_items", "")
            desc = f"{merchant}: {non_deduct_items}" if non_deduct_items else f"{merchant} (Privat)"
            suggestions.append({
                "document_id": document.id,
                "document_type": str(document.document_type.value) if hasattr(document.document_type, 'value') else str(document.document_type),
                "transaction_type": TransactionType.EXPENSE.value,
                "amount": str(non_deduct_amt),
                "date": date_str,
                "description": desc[:500],
                "category": "groceries",
                "is_deductible": False,
                "deduction_reason": non_deduct_reason[:500],
                "confidence": 0.85,
                "needs_review": False,
                "classification_method": classification.get("classification_method"),
                "classification_rule_id": classification.get("classification_rule_id"),
                "deductibility_rule_id": classification.get("deductibility_rule_id"),
                "applied_rule_sources": classification.get("applied_rule_sources", []),
                "canonical_description": classification.get("canonical_description"),
                "extracted_fields": {},
            })

        if not suggestions:
            return [
                self._build_single_suggestion(
                    document,
                    transaction_data,
                    classification,
                    ocr_data,
                    direction_resolution=direction_resolution,
                )
            ]

        suggestions = [
            self._annotate_suggestion_with_direction(suggestion, direction_resolution)
            for suggestion in suggestions
        ]

        logger.info(
            "Split receipt %d into %d transactions: deductible=€%.2f, non-deductible=€%.2f",
            document.id, len(suggestions), deduct_amt, non_deduct_amt,
        )
        return suggestions

    def create_transaction_from_suggestion(
        self, suggestion: Dict[str, Any], user_id: int
    ) -> Transaction:
        """Backward-compatible wrapper that returns only the transaction object."""
        return self.create_transaction_from_suggestion_with_result(suggestion, user_id).transaction

    def create_transaction_from_suggestion_with_result(
        self, suggestion: Dict[str, Any], user_id: int
    ) -> OCRTransactionCreationResult:
        """
        Create an actual transaction from a suggestion
        
        Args:
            suggestion: Transaction suggestion dictionary
            user_id: User ID
            
        Returns:
            Transaction creation result, including duplicate detection outcome
        """
        direction_resolution = self._enforce_direction_gate(suggestion, user_id)
        suggestion = self._annotate_suggestion_with_direction(
            dict(suggestion),
            direction_resolution,
        )
        transaction_type, category, txn_date = self._parse_transaction_fields(suggestion)
        amount = normalize_amount(suggestion.get("amount"))
        if amount is None:
            raise ValueError(f"Invalid amount value: {suggestion.get('amount')}")
        description = suggestion["description"]

        duplicate_detector = getattr(self, "duplicate_detector", None)
        if duplicate_detector is None:
            duplicate_detector = DuplicateDetector(self.db)
            self.duplicate_detector = duplicate_detector

        is_duplicate, matching_transaction = duplicate_detector.check_duplicate(
            user_id=user_id,
            transaction_date=txn_date,
            amount=amount,
            description=description,
        )
        if is_duplicate and matching_transaction:
            duplicate_confidence = round(
                duplicate_detector._calculate_similarity(
                    description,
                    matching_transaction.description,
                ),
                2,
            )
            logger.info(
                "Skipped duplicate OCR transaction for document %s; reusing transaction %s",
                suggestion.get("document_id"),
                matching_transaction.id,
            )
            # Back-fill document.transaction_id so the document is linked even on duplicate-reuse
            doc_id = suggestion.get("document_id")
            if doc_id:
                doc = self.db.query(Document).filter(Document.id == doc_id).first()
                if doc and not doc.transaction_id:
                    doc.transaction_id = matching_transaction.id
                    if isinstance(doc.ocr_result, dict):
                        materialize_final_transaction_type(
                            document=doc,
                            ocr_result=doc.ocr_result,
                            db=self.db,
                            transaction=matching_transaction,
                        )
                    self.db.commit()
            return OCRTransactionCreationResult(
                transaction=matching_transaction,
                created=False,
                duplicate_of_id=matching_transaction.id,
                duplicate_confidence=duplicate_confidence,
            )

        transaction = self._create_transaction_record(
            suggestion=suggestion,
            user_id=user_id,
            transaction_type=transaction_type,
            category=category,
            txn_date=txn_date,
            amount=amount,
        )
        return OCRTransactionCreationResult(transaction=transaction, created=True)

    def _parse_transaction_fields(
        self,
        suggestion: Dict[str, Any],
    ) -> tuple[TransactionType, Optional[IncomeCategory | ExpenseCategory], Any]:
        """Parse normalized transaction fields from a suggestion payload."""
        transaction_type = (
            coerce_transaction_type(
                suggestion.get("transaction_type"),
                default=TransactionType.EXPENSE,
            )
            or TransactionType.EXPENSE
        )
        category = self._coerce_category(transaction_type, suggestion.get("category"))

        raw_date = suggestion.get("date")
        if raw_date:
            normalized_date = normalize_date(raw_date)
            if normalized_date is not None:
                txn_date = normalized_date
            elif isinstance(raw_date, datetime):
                txn_date = raw_date.date()
            elif hasattr(raw_date, 'date'):
                txn_date = raw_date
            else:
                txn_date = datetime.utcnow().date()
        else:
            txn_date = datetime.utcnow().date()

        return transaction_type, category, txn_date

    def _coerce_category(
        self,
        transaction_type: TransactionType,
        raw_category: Any,
    ) -> Optional[IncomeCategory | ExpenseCategory]:
        """Normalize OCR/LLM categories to model enums without breaking auto-create."""
        if not raw_category:
            return None

        if transaction_type == TransactionType.INCOME:
            category = coerce_income_category(
                raw_category,
            )
        else:
            category = coerce_expense_category(
                raw_category,
            )

        if category is None:
            default = IncomeCategory.OTHER_INCOME if transaction_type == TransactionType.INCOME else ExpenseCategory.OTHER
            logger.warning(
                "Unknown OCR %s category '%s'; falling back to %s",
                transaction_type.value,
                raw_category,
                default.value,
            )
            return default

        return category

    def _create_transaction_record(
        self,
        *,
        suggestion: Dict[str, Any],
        user_id: int,
        transaction_type: TransactionType,
        category: Optional[IncomeCategory | ExpenseCategory],
        txn_date: Any,
        amount: Decimal,
    ) -> Transaction:
        """Persist a new OCR transaction after all validations have passed."""
        transaction = Transaction(
            user_id=user_id,
            type=transaction_type,
            amount=amount,
            transaction_date=txn_date,
            description=suggestion["description"],
            income_category=category if transaction_type == TransactionType.INCOME else None,
            expense_category=category if transaction_type == TransactionType.EXPENSE else None,
            is_deductible=suggestion.get("is_deductible", False),
            deduction_reason=suggestion.get("deduction_reason"),
            document_id=suggestion["document_id"],
            import_source="ocr",
            classification_confidence=Decimal(str(suggestion.get("confidence", 0.5))),
            classification_method=suggestion.get("classification_method"),
            needs_review=suggestion.get("needs_review", True),
            reviewed=suggestion.get("reviewed", False),
        )
        
        self.db.add(transaction)
        self.db.flush()

        explicit_line_items = suggestion.get("line_items")
        if explicit_line_items:
            normalized_line_items = normalize_line_item_payloads(
                transaction_type=transaction.type,
                transaction_amount=transaction.amount,
                description=transaction.description,
                income_category=transaction.income_category,
                expense_category=transaction.expense_category,
                is_deductible=transaction.is_deductible,
                deduction_reason=transaction.deduction_reason,
                vat_rate=transaction.vat_rate,
                vat_amount=transaction.vat_amount,
                line_items=explicit_line_items,
                default_allocation_source=LineItemAllocationSource.OCR_SPLIT,
            )
            replace_transaction_line_items(self.db, transaction, normalized_line_items)

        self.db.commit()
        self.db.refresh(transaction)
        
        # Update document with transaction link
        document = self.db.query(Document).filter(Document.id == suggestion["document_id"]).first()
        if document and not document.transaction_id:
            document.transaction_id = transaction.id
            if isinstance(document.ocr_result, dict):
                materialize_final_transaction_type(
                    document=document,
                    ocr_result=document.ocr_result,
                    db=self.db,
                    transaction=transaction,
                )
            self.db.commit()

        # Sync line items from document OCR data to transaction_line_items
        if not explicit_line_items:
            self._sync_line_items_from_document(transaction, suggestion)
        if not transaction.line_items:
            mirror = build_mirror_line_item_payload(
                transaction_type=transaction.type,
                amount=transaction.amount,
                description=transaction.description,
                income_category=transaction.income_category,
                expense_category=transaction.expense_category,
                is_deductible=transaction.is_deductible,
                deduction_reason=transaction.deduction_reason,
                vat_rate=transaction.vat_rate,
                vat_amount=transaction.vat_amount,
                allocation_source=LineItemAllocationSource.OCR_SPLIT,
            )
            self.db.add(
                TransactionLineItem(
                    transaction_id=transaction.id,
                    description=mirror["description"],
                    amount=mirror["amount"],
                    quantity=mirror["quantity"],
                    posting_type=mirror["posting_type"],
                    allocation_source=mirror["allocation_source"],
                    category=mirror.get("category"),
                    is_deductible=mirror["is_deductible"],
                    deduction_reason=mirror.get("deduction_reason"),
                    vat_rate=mirror.get("vat_rate"),
                    vat_amount=mirror.get("vat_amount"),
                    vat_recoverable_amount=mirror["vat_recoverable_amount"],
                    rule_bucket=mirror.get("rule_bucket"),
                    classification_method=transaction.classification_method,
                    sort_order=0,
                )
            )
            self.db.commit()
            self.db.refresh(transaction)
        
        logger.info(f"Created transaction {transaction.id} from OCR document {suggestion['document_id']}")
        
        return transaction

    def _sync_line_items_from_document(
        self, transaction: Transaction, suggestion: Dict[str, Any]
    ) -> None:
        """Copy line items from OCR data into transaction_line_items table."""
        # Try multiple sources for line items
        doc_line_items = suggestion.get("extracted_fields", {}).get("line_items") or []
        if not doc_line_items:
            doc = (
                self.db.query(Document)
                .filter(Document.id == suggestion.get("document_id"))
                .first()
            )
            if doc and doc.ocr_result:
                ocr = doc.ocr_result if isinstance(doc.ocr_result, dict) else {}
                tax_items = ocr.get("tax_analysis", {}).get("items")
                if tax_items:
                    doc_line_items = tax_items
                else:
                    doc_line_items = ocr.get("items") or ocr.get("line_items") or []

        if not doc_line_items or len(doc_line_items) < 2:
            return

        try:
            posting_type = default_posting_type_for_transaction_type(transaction.type)
            fallback_category = (
                transaction.expense_category.value
                if transaction.expense_category and hasattr(transaction.expense_category, "value")
                else (
                    transaction.income_category.value
                    if transaction.income_category and hasattr(transaction.income_category, "value")
                    else None
                )
            )
            for idx, li in enumerate(doc_line_items):
                desc = li.get("description") or li.get("name") or f"Item {idx + 1}"
                quantity = normalize_quantity(li.get("quantity", 1)) or 1
                normalized_amount = None
                for unit_candidate in (
                    li.get("unit_price"),
                    li.get("price"),
                    li.get("unit_amount"),
                    li.get("amount"),
                ):
                    normalized_amount = normalize_amount(unit_candidate)
                    if normalized_amount is not None:
                        break
                if normalized_amount is None:
                    for total_candidate in (
                        li.get("total_price"),
                        li.get("total"),
                        li.get("line_total"),
                        li.get("gross_total"),
                        li.get("net_total"),
                    ):
                        normalized_total = normalize_amount(total_candidate)
                        if normalized_total is None:
                            continue
                        if quantity > 1:
                            normalized_amount = normalized_total / Decimal(quantity)
                        else:
                            normalized_amount = normalized_total
                        break
                if normalized_amount is None:
                    continue
                vat_rate_raw = li.get("vat_rate")
                vat_rate = None
                if vat_rate_raw is not None:
                    vr = normalize_vat_rate(vat_rate_raw)
                    if vr is not None:
                        vat_rate = vr / 100 if vr > 1 else vr
                vat_amount_raw = li.get("vat_amount")
                normalized_vat_amount = normalize_amount(vat_amount_raw) if vat_amount_raw else None
                deductible_flag = normalize_boolean_flag(li.get("is_deductible"))
                semantic_flags = normalize_semantic_flags(
                    li.get("semantic_flags"),
                    desc,
                    li.get("status"),
                    li.get("note"),
                )
                item = TransactionLineItem(
                    transaction_id=transaction.id,
                    description=desc,
                    amount=normalized_amount,
                    quantity=quantity,
                    posting_type=posting_type,
                    allocation_source=LineItemAllocationSource.OCR_SPLIT,
                    category=li.get("category") or fallback_category,
                    is_deductible=(
                        (
                            deductible_flag
                            if deductible_flag is not None
                            else li.get("is_deductible", transaction.is_deductible)
                        )
                        if posting_type.value == "expense"
                        else False
                    ),
                    deduction_reason=li.get("deduction_reason"),
                    vat_rate=vat_rate,
                    vat_amount=normalized_vat_amount,
                    vat_recoverable_amount=Decimal("0.00"),
                    classification_method=transaction.classification_method,
                    sort_order=idx,
                )
                # Keep normalized hints available in-memory for debugging during the transaction lifecycle.
                li["currency"] = (
                    normalize_currency(li.get("currency"))
                    or normalize_currency(li.get("amount"))
                    or normalize_currency(li.get("total_price"))
                    or normalize_currency(li.get("total"))
                )
                li["semantic_flags"] = semantic_flags
                self.db.add(item)
            self.db.commit()
            self.db.refresh(transaction)
        except Exception as e:
            logger.warning(
                "Failed to sync line items for transaction %s: %s", transaction.id, e
            )
            self.db.rollback()

    def _extract_transaction_data(
        self, document: Document, ocr_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract transaction data from OCR results based on document type"""
        # document_type may be enum or string
        doc_type = str(document.document_type.value) if hasattr(document.document_type, 'value') else str(document.document_type)
        
        if doc_type == DocumentType.RECEIPT.value:
            return self._extract_from_receipt(ocr_data)
        elif doc_type == DocumentType.INVOICE.value:
            return self._extract_from_invoice(ocr_data)
        elif doc_type == DocumentType.PAYSLIP.value:
            return self._extract_from_payslip(ocr_data)
        elif doc_type == DocumentType.LOHNZETTEL.value:
            return self._extract_from_lohnzettel(ocr_data)
        elif doc_type == DocumentType.SVS_NOTICE.value:
            return self._extract_from_svs_notice(ocr_data)
        elif doc_type == DocumentType.EINKOMMENSTEUERBESCHEID.value:
            return self._extract_from_bescheid(ocr_data)
        else:
            return self._extract_generic(ocr_data)

    def _extract_from_receipt(self, ocr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction data from receipt OCR"""
        amount = ocr_data.get("amount")
        date = ocr_data.get("date")
        merchant = ocr_data.get("merchant", "Unknown merchant")
        product_summary = ocr_data.get("product_summary")
        vlm_description = ocr_data.get("description")
        line_items = ocr_data.get("line_items") or ocr_data.get("items") or []

        if not amount:
            return None

        # Build description from best available source
        if vlm_description and len(vlm_description) > 10:
            description = f"{merchant}: {vlm_description}"
        elif product_summary:
            description = f"{merchant}: {product_summary}"
        elif line_items:
            # Summarize from line items
            item_names = [it.get("name", "") for it in line_items[:5] if it.get("name")]
            if item_names:
                summary = ", ".join(item_names)
                if len(line_items) > 5:
                    summary += f" (+{len(line_items) - 5} more)"
                description = f"{merchant}: {summary}"
            else:
                description = f"Purchase at {merchant}"
        else:
            description = f"Purchase at {merchant}"

        normalized_amount = normalize_amount(amount)
        normalized_date = normalize_date(date)
        if normalized_amount is None:
            return None

        return {
            "amount": normalized_amount,
            "date": normalized_date or date,
            "description": description,
        }

    def _extract_from_invoice(self, ocr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction data from invoice OCR"""
        amount = ocr_data.get("amount")
        date = ocr_data.get("date")
        supplier = (
            ocr_data.get("supplier")
            or ocr_data.get("merchant")
            or "Unknown supplier"
        )
        invoice_number = ocr_data.get("invoice_number", "")
        product_summary = ocr_data.get("product_summary")

        if not amount:
            return None

        # Build a meaningful description
        if product_summary:
            description = f"{supplier}: {product_summary}"
        else:
            description = f"Invoice from {supplier}"
        if invoice_number:
            description += f" (#{invoice_number})"

        normalized_amount = normalize_amount(amount)
        normalized_date = normalize_date(date)
        if normalized_amount is None:
            return None

        return {
            "amount": normalized_amount,
            "date": normalized_date or date,
            "description": description,
        }

    def _extract_from_payslip(self, ocr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction data from payslip OCR"""
        # Use net income (Netto) for the transaction
        amount = ocr_data.get("net_income") or ocr_data.get("amount")
        date = ocr_data.get("date")
        employer = ocr_data.get("employer", "Employer")
        
        if not amount:
            return None
        
        normalized_amount = normalize_amount(amount)
        normalized_date = normalize_date(date)
        if normalized_amount is None:
            return None

        return {
            "amount": normalized_amount,
            "date": normalized_date or date,
            "description": f"Salary from {employer}",
        }

    def _extract_from_lohnzettel(self, ocr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction data from Lohnzettel (wage tax card)"""
        gross_income = ocr_data.get("gross_income")
        date = ocr_data.get("date")
        employer = ocr_data.get("employer", "Employer")

        if not gross_income:
            return None

        normalized_amount = normalize_amount(gross_income)
        normalized_date = normalize_date(date)
        if normalized_amount is None:
            return None

        return {
            "amount": normalized_amount,
            "date": normalized_date or date,
            "description": f"Salary from {employer}",
        }


    def _extract_from_svs_notice(self, ocr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction data from SVS contribution notice.

        Three cases:
        - Beitragsvorschreibung: amount/beitrag_gesamt → expense
        - Nachbemessung nachzahlung: nachzahlung → expense
        - Nachbemessung gutschrift: gutschrift → income
        """
        date = ocr_data.get("date")
        normalized_date = normalize_date(date)

        # Case 1: Gutschrift (refund from final assessment) → income
        gutschrift = ocr_data.get("gutschrift")
        if gutschrift:
            amt = normalize_amount(gutschrift)
            if amt and amt > 0:
                # Check there's no regular beitrag_gesamt (which would mean
                # it's a regular notice that just mentions gutschrift rules)
                beitrag = normalize_amount(ocr_data.get("amount") or ocr_data.get("beitrag_gesamt"))
                if not beitrag:
                    return {
                        "amount": amt,
                        "date": normalized_date or date,
                        "description": "SVS Nachbemessung Gutschrift",
                        "_svs_is_gutschrift": True,
                    }

        # Case 2: Nachzahlung (back-payment from final assessment) → expense
        nachzahlung = ocr_data.get("nachzahlung")
        if nachzahlung:
            amt = normalize_amount(nachzahlung)
            if amt and amt > 0:
                beitrag = normalize_amount(ocr_data.get("amount") or ocr_data.get("beitrag_gesamt"))
                if not beitrag:
                    return {
                        "amount": amt,
                        "date": normalized_date or date,
                        "description": "SVS Nachbemessung Nachzahlung",
                    }

        # Case 3: Regular Beitragsvorschreibung → expense
        amount = ocr_data.get("amount") or ocr_data.get("beitrag_gesamt") or ocr_data.get("contribution_amount")
        if not amount:
            return None

        normalized_amount = normalize_amount(amount)
        if normalized_amount is None:
            return None

        quarter = ocr_data.get("quarter", "")
        tax_year = ocr_data.get("tax_year", "")
        desc = f"SVS Beitragsvorschreibung Q{quarter}/{tax_year}" if quarter and tax_year else "SVS Beitragsvorschreibung"

        return {
            "amount": normalized_amount,
            "date": normalized_date or date,
            "description": desc,
        }

    def _extract_from_bescheid(self, ocr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract primary transaction from Einkommensteuerbescheid OCR data"""
        einkommen = ocr_data.get("einkommen")
        tax_year = ocr_data.get("tax_year")
        taxpayer = ocr_data.get("taxpayer_name", "")

        if not einkommen:
            return None

        from datetime import date as date_cls

        ref_date = date_cls(tax_year, 12, 31) if tax_year else None
        description = f"Einkommen {tax_year}" if tax_year else "Einkommen lt. Bescheid"
        if taxpayer:
            description += f" - {taxpayer}"

        normalized_amount = normalize_amount(einkommen)
        if normalized_amount is None:
            return None

        return {
            "amount": normalized_amount,
            "date": ref_date,
            "description": description,
        }

    def _extract_generic(self, ocr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction data from generic document"""
        amount = ocr_data.get("amount")
        date = ocr_data.get("date")
        supplier = (
            ocr_data.get("supplier")
            or ocr_data.get("merchant")
        )
        product_summary = ocr_data.get("product_summary")

        if not amount:
            return None

        if product_summary and supplier:
            description = f"{supplier}: {product_summary}"
        elif supplier:
            description = f"Transaction from {supplier}"
        elif product_summary:
            description = product_summary
        else:
            description = "Transaction from document"

        normalized_amount = normalize_amount(amount)
        normalized_date = normalize_date(date)
        if normalized_amount is None:
            return None

        return {
            "amount": normalized_amount,
            "date": normalized_date or date,
            "description": description,
        }

    def _classify_from_ocr(
        self,
        document: Document,
        transaction_data: Dict[str, Any],
        user_id: int,
        *,
        direction_resolution: Optional[TransactionDirectionResolution] = None,
    ) -> Dict[str, Any]:
        """Classify transaction based on document type and OCR data"""
        doc_type = str(document.document_type.value) if hasattr(document.document_type, 'value') else str(document.document_type)
        
        if doc_type in [DocumentType.PAYSLIP.value, DocumentType.LOHNZETTEL.value]:
            return {
                "transaction_type": TransactionType.INCOME.value,
                "category": IncomeCategory.EMPLOYMENT.value,
                "is_deductible": False,
                "deduction_reason": "Income is not deductible",
                "confidence": 0.95,
            }

        elif doc_type == DocumentType.RENTAL_CONTRACT.value:
            return {
                "transaction_type": TransactionType.INCOME.value,
                "category": IncomeCategory.RENTAL.value,
                "is_deductible": False,
                "deduction_reason": "Rental income is not deductible",
                "confidence": 0.90,
            }
            
        elif doc_type == DocumentType.SVS_NOTICE.value:
            # Gutschrift (refund) → income; otherwise → expense
            is_gutschrift = transaction_data.get("_svs_is_gutschrift", False)
            if is_gutschrift:
                return {
                    "transaction_type": TransactionType.INCOME.value,
                    "category": IncomeCategory.OTHER.value,
                    "is_deductible": False,
                    "deduction_reason": "SVS Gutschrift (Nachbemessung refund)",
                    "confidence": 0.90,
                }
            return {
                "transaction_type": TransactionType.EXPENSE.value,
                "category": ExpenseCategory.INSURANCE.value,
                "is_deductible": True,
                "deduction_reason": "SVS contributions are deductible as Sonderausgaben",
                "confidence": 0.95,
            }

        elif doc_type == DocumentType.EINKOMMENSTEUERBESCHEID.value:
            return {
                "transaction_type": TransactionType.INCOME.value,
                "category": IncomeCategory.EMPLOYMENT.value,
                "is_deductible": False,
                "deduction_reason": "Einkommensteuerbescheid - total income from tax assessment",
                "confidence": 0.90,
            }
            
        elif doc_type in [DocumentType.RECEIPT.value, DocumentType.INVOICE.value]:
            resolved_direction = direction_resolution.candidate if direction_resolution else "unknown"
            transaction_type = (
                TransactionType.INCOME
                if resolved_direction == "income"
                else TransactionType.EXPENSE
            )

            user = load_sensitive_user_context(self.db, user_id)
            method = "unknown"
            deduct_requires_review = True
            ocr_data = document.ocr_result if isinstance(document.ocr_result, dict) else {}
            canonical_description = build_ocr_parent_description(
                merchant=ocr_data.get("merchant") or ocr_data.get("supplier"),
                ocr_description=ocr_data.get("description") or ocr_data.get("product_summary"),
                fallback_description=transaction_data.get("description"),
            )
            line_items = ocr_data.get("line_items") or ocr_data.get("items") or []
            rule_resolver = getattr(self, "rule_resolver", None)
            if rule_resolver is None and self.db is not None:
                rule_resolver = TransactionRuleResolver(self.db)
                self.rule_resolver = rule_resolver

            if user:
                description = transaction_data.get("description", "")
                resolved_rules = (
                    rule_resolver.resolve(
                        user_id=user_id,
                        context="ocr_receipt",
                        txn_type=transaction_type.value,
                        canonical_description=canonical_description,
                        line_items=line_items,
                        ocr_category=None,
                    )
                    if rule_resolver is not None
                    else None
                )

                temp_transaction = Transaction(
                    user_id=user_id,
                    type=transaction_type,
                    amount=transaction_data["amount"],
                    transaction_date=transaction_data["date"] or datetime.utcnow().date(),
                    description=canonical_description or description,
                )

                classification = self.classifier.classify_transaction(
                    temp_transaction,
                    user,
                    allow_user_override=False,
                )
                category = (
                    resolved_rules.resolved_category
                    if resolved_rules and resolved_rules.resolved_category
                    else classification.category if classification.category else None
                )
                # Override transaction_type if rule says different direction
                if resolved_rules and resolved_rules.resolved_txn_type:
                    rule_txn_type = resolved_rules.resolved_txn_type
                    if rule_txn_type == "income":
                        transaction_type = TransactionType.INCOME
                    elif rule_txn_type == "expense":
                        transaction_type = TransactionType.EXPENSE
                method = (
                    resolved_rules.classification_method
                    if resolved_rules and resolved_rules.classification_method
                    else classification.method if hasattr(classification, 'method') else 'unknown'
                )
                semantics = direction_resolution.semantics if direction_resolution else "unknown"

                if transaction_type == TransactionType.INCOME:
                    is_deductible = False
                    deduction_reason = "Income is not deductible"
                    deduct_requires_review = False
                    if semantics == "credit_note":
                        deduction_reason = "Credit note / reversal of prior income"
                    elif semantics == "proforma":
                        deduction_reason = "Proforma document requires manual confirmation"
                        deduct_requires_review = True
                    elif semantics == "delivery_note":
                        deduction_reason = "Delivery note requires manual confirmation"
                        deduct_requires_review = True
                elif category:
                    if (
                        resolved_rules is not None
                        and resolved_rules.resolved_is_deductible is not None
                    ):
                        is_deductible = resolved_rules.resolved_is_deductible
                        deduction_reason = (
                            resolved_rules.resolved_deduction_reason
                            or "Learned from your previous correction"
                        )
                        deduct_requires_review = False
                    # If LLM already provided deductibility, use it directly
                    elif method == 'llm' and hasattr(classification, 'is_deductible') and classification.is_deductible is not None:
                        is_deductible = classification.is_deductible
                        deduction_reason = getattr(classification, 'deduction_reason', '') or ''
                        deduct_requires_review = False
                    else:
                        user_type_val = user.user_type.value if hasattr(user.user_type, 'value') else str(user.user_type or "employee")
                        deduct_result = self.deductibility_checker.check(
                            category, user_type_val,
                            ocr_data=ocr_data,
                            description=canonical_description or description,
                            business_type=getattr(user, 'business_type', None),
                            business_industry=getattr(user, 'business_industry', None),
                            user_id=user_id,
                            allow_user_override=False,
                        )
                        is_deductible = deduct_result.is_deductible
                        deduction_reason = deduct_result.reason
                        if deduct_result.tax_tip:
                            deduction_reason = f"{deduct_result.reason} | {deduct_result.tax_tip}"
                        deduct_requires_review = deduct_result.requires_review
                    if semantics == "credit_note":
                        deduction_reason = f"Credit note / reversal of prior expense | {deduction_reason}"
                    elif semantics == "proforma":
                        deduction_reason = "Proforma document requires manual confirmation"
                        deduct_requires_review = True
                    elif semantics == "delivery_note":
                        deduction_reason = "Delivery note requires manual confirmation"
                        deduct_requires_review = True
                else:
                    is_deductible = False
                    deduction_reason = "Unable to determine deductibility"
                    deduct_requires_review = True
                confidence = (
                    resolved_rules.classification_confidence
                    if resolved_rules and resolved_rules.classification_confidence is not None
                    else classification.confidence
                )
            else:
                category = None
                is_deductible = False
                deduction_reason = "Unable to determine deductibility"
                confidence = 0.5
                method = "unknown"
                deduct_requires_review = True
                resolved_rules = None
                
            return {
                "transaction_type": transaction_type.value,
                "category": category,
                "is_deductible": is_deductible,
                "deduction_reason": deduction_reason,
                "confidence": confidence,
                "classification_method": method,
                "requires_review": deduct_requires_review,
                "classification_rule_id": (
                    resolved_rules.classification_rule_id
                    if resolved_rules is not None
                    else None
                ),
                "deductibility_rule_id": (
                    resolved_rules.deductibility_rule_id
                    if resolved_rules is not None
                    else None
                ),
                "applied_rule_sources": (
                    list(resolved_rules.applied_sources)
                    if resolved_rules is not None
                    else []
                ),
                "canonical_description": canonical_description,
            }
        else:
            return {
                "transaction_type": TransactionType.EXPENSE.value,
                "category": None,
                "is_deductible": False,
                "deduction_reason": "Unable to determine deductibility",
                "confidence": 0.3,
            }



