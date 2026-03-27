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
            ocr_data["_file_name"] = document.file_name or ""
            ocr_data["_user_id"] = document.user_id
            return self._extract_from_svs_notice(ocr_data)
        elif doc_type == DocumentType.EINKOMMENSTEUERBESCHEID.value:
            return self._extract_from_bescheid(ocr_data)
        elif doc_type == DocumentType.KIRCHENBEITRAG.value:
            return self._extract_from_kirchenbeitrag(ocr_data)
        elif doc_type == DocumentType.SPENDENBESTAETIGUNG.value:
            return self._extract_from_spendenbestaetigung(ocr_data)
        elif doc_type == DocumentType.FORTBILDUNGSKOSTEN.value:
            # Fortbildungskosten is essentially a receipt/invoice for training
            return self._extract_from_receipt(ocr_data)
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


    # SVS subtypes that should create transactions
    _SVS_TRANSACTION_SUBTYPES = {"vorschreibung", "nachforderung", "gutschrift", "saeumniszuschlag"}
    # SVS subtypes that should NOT create transactions (just store metadata)
    _SVS_NO_TRANSACTION_SUBTYPES = {
        "kontoauszug", "herabsetzung", "versicherungspflicht",
        "mindestbeitrag", "zahlungserinnerung", "kontobestaetigung", "befreiung",
    }

    def _extract_from_svs_notice(self, ocr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction data from SVS document based on VLM svs_subtype.

        Uses VLM-classified svs_subtype to dispatch:
        - vorschreibung → expense (with dedup check)
        - nachforderung → expense (stores beitragsjahr)
        - gutschrift → income (insurance refund)
        - saeumniszuschlag → expense (NOT deductible)
        - ratenzahlung → creates monthly recurring (returns None for transaction)
        - all others → None (no transaction)

        If svs_subtype is missing → returns None (manual review fallback)
        """
        svs_subtype = str(ocr_data.get("svs_subtype") or "").strip().lower()
        date = ocr_data.get("date")
        normalized_date = normalize_date(date)
        tax_year = ocr_data.get("tax_year", "")
        quarter = ocr_data.get("quarter", "")
        beitragsjahr = ocr_data.get("beitragsjahr") or tax_year

        # -- Fallback: no svs_subtype from VLM → try to infer from legacy signals --
        if not svs_subtype:
            svs_subtype = self._infer_svs_subtype_legacy(ocr_data)

        # -- No subtype at all → manual review --
        if not svs_subtype:
            logger.info("SVS subtype unknown — returning None for manual review")
            return None

        logger.info("SVS subtype determined: %s", svs_subtype)

        # Store subtype in ocr_data for downstream use
        ocr_data["_svs_subtype"] = svs_subtype

        # -- Subtypes that don't create transactions --
        if svs_subtype in self._SVS_NO_TRANSACTION_SUBTYPES:
            logger.info("SVS subtype '%s' — no transaction creation", svs_subtype)
            return None

        # -- Ratenzahlung: create recurring instead of transaction --
        if svs_subtype == "ratenzahlung":
            self._create_svs_ratenzahlung_recurring(ocr_data)
            return None

        # -- Vorschreibung: regular quarterly contribution --
        if svs_subtype == "vorschreibung":
            amount = ocr_data.get("amount") or ocr_data.get("beitrag_gesamt")
            if not amount:
                return None
            normalized_amount = normalize_amount(amount)
            if normalized_amount is None:
                return None

            # Dedup check: same user + quarter + year + amount
            if self._svs_vorschreibung_exists(ocr_data, normalized_amount):
                logger.info(
                    "SVS Vorschreibung Q%s/%s already exists — skipping",
                    quarter, tax_year,
                )
                return None

            desc = f"SVS Beitragsvorschreibung Q{quarter}/{tax_year}" if quarter and tax_year else "SVS Beitragsvorschreibung"
            return {
                "amount": normalized_amount,
                "date": normalized_date or date,
                "description": desc,
                "_svs_subtype": "vorschreibung",
            }

        # -- Nachforderung: back-payment from Nachbemessung --
        if svs_subtype == "nachforderung":
            amount = (
                ocr_data.get("nachzahlung")
                or ocr_data.get("amount")
                or ocr_data.get("beitrag_gesamt")
            )
            if not amount:
                return None
            normalized_amount = normalize_amount(amount)
            if normalized_amount is None or normalized_amount <= 0:
                return None
            desc = f"SVS Nachbemessung Nachforderung"
            if beitragsjahr:
                desc += f" (Beitragsjahr {beitragsjahr})"
            return {
                "amount": normalized_amount,
                "date": normalized_date or date,
                "description": desc,
                "_svs_subtype": "nachforderung",
                "_beitragsjahr": beitragsjahr,
            }

        # -- Gutschrift: refund from Nachbemessung --
        if svs_subtype == "gutschrift":
            amount = (
                ocr_data.get("gutschrift")
                or ocr_data.get("amount")
                or ocr_data.get("beitrag_gesamt")
            )
            if not amount:
                return None
            normalized_amount = normalize_amount(amount)
            if normalized_amount is None or normalized_amount <= 0:
                return None
            desc = f"SVS Nachbemessung Gutschrift"
            if beitragsjahr:
                desc += f" (Beitragsjahr {beitragsjahr})"
            return {
                "amount": normalized_amount,
                "date": normalized_date or date,
                "description": desc,
                "_svs_subtype": "gutschrift",
                "_svs_is_gutschrift": True,
                "_beitragsjahr": beitragsjahr,
            }

        # -- Säumniszuschlag: late penalty (NOT deductible) --
        if svs_subtype == "saeumniszuschlag":
            # Try dedicated penalty amount field first, then extract from text
            amount = (
                ocr_data.get("saeumniszuschlag_betrag")
                or ocr_data.get("zuschlag")
                or ocr_data.get("penalty_amount")
            )
            # Try extracting from raw_text: "Säumniszuschlag ... EUR XX,XX"
            if not amount:
                import re
                raw = str(ocr_data.get("raw_text") or "")
                m = re.search(
                    r'(?:s[aä]umniszuschlag|zuschlag)[^€\d]*(?:EUR\s*)?(\d[\d.,]*)',
                    raw, re.IGNORECASE,
                )
                if m:
                    amount = m.group(1)
            # Cannot determine penalty amount → return None for manual review
            # (amount/beitrag_gesamt is the base contribution, NOT the penalty)
            if not amount:
                logger.info("SVS Säumniszuschlag: penalty amount not extractable — needs manual review")
                return None
            normalized_amount = normalize_amount(amount)
            if normalized_amount is None or normalized_amount <= 0:
                return None
            result = {
                "amount": normalized_amount,
                "date": normalized_date or date,
                "description": "SVS Säumniszuschlag",
                "_svs_subtype": "saeumniszuschlag",
            }
            if needs_review:
                result["_needs_amount_review"] = True
            return result

        # Unknown subtype → manual review
        logger.warning("Unknown SVS subtype '%s' — returning None", svs_subtype)
        return None

    def _infer_svs_subtype_legacy(self, ocr_data: Dict[str, Any]) -> str:
        """Fallback: infer SVS subtype from legacy field signals when VLM doesn't return svs_subtype."""
        file_name = str(ocr_data.get("_file_name") or "").lower()
        desc = str(ocr_data.get("description") or "").lower()
        raw = str(ocr_data.get("raw_text") or "")[:2000].lower()
        all_text = file_name + " " + desc + " " + raw

        if any(m in all_text for m in ("kontobestätigung", "kontobestaetigung", "kontobestatigung")):
            return "kontobestaetigung"
        if any(m in all_text for m in ("kontoauszug", "beitragskontoauszug")):
            return "kontoauszug"
        if "säumniszuschlag" in all_text or "saeumniszuschlag" in all_text:
            return "saeumniszuschlag"
        if "herabsetzung" in all_text:
            return "herabsetzung"
        if "befreiung" in all_text or "befreit" in all_text:
            return "befreiung"
        if "ratenzahlung" in all_text or "ratenvereinbarung" in all_text:
            return "ratenzahlung"
        if "zahlungserinnerung" in all_text or "mahnung" in all_text:
            return "zahlungserinnerung"
        if "versicherungspflicht" in all_text:
            return "versicherungspflicht"
        if "mindestbeitragsgrundlage" in all_text:
            return "mindestbeitrag"

        # Field-based inference
        if ocr_data.get("gutschrift") and not ocr_data.get("beitrag_gesamt"):
            return "gutschrift"
        if ocr_data.get("nachzahlung") and not ocr_data.get("beitrag_gesamt"):
            return "nachforderung"
        if ocr_data.get("gutschrift") or ocr_data.get("nachzahlung"):
            # Has both gutschrift/nachzahlung AND beitrag_gesamt — likely Nachbemessung
            if ocr_data.get("nachzahlung"):
                return "nachforderung"
            return "gutschrift"

        # Default: if has beitrag_gesamt and quarter → vorschreibung
        if ocr_data.get("beitrag_gesamt") and ocr_data.get("quarter"):
            return "vorschreibung"

        return ""  # Unknown

    def _svs_vorschreibung_exists(self, ocr_data: Dict[str, Any], amount: float) -> bool:
        """Check if an SVS Vorschreibung for the same quarter already exists."""
        quarter = ocr_data.get("quarter")
        tax_year = ocr_data.get("tax_year")
        if not quarter or not tax_year:
            return False

        try:
            from app.models.transaction import Transaction, TransactionType
            existing = self.db.query(Transaction).filter(
                Transaction.user_id == self._current_user_id if hasattr(self, '_current_user_id') else True,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.description.ilike(f"%SVS%Q{quarter}%{tax_year}%"),
            ).first()
            return existing is not None
        except Exception:
            return False

    def _create_svs_ratenzahlung_recurring(self, ocr_data: Dict[str, Any]) -> None:
        """Create a monthly recurring transaction for SVS Ratenzahlung (installment plan)."""
        try:
            import re
            ratenanzahl = int(ocr_data.get("ratenanzahl") or 0)
            ratenbetrag = normalize_amount(ocr_data.get("ratenbetrag") or ocr_data.get("amount"))

            # Try extracting from raw_text if VLM didn't provide the fields
            if (not ratenanzahl or not ratenbetrag) and ocr_data.get("raw_text"):
                raw = str(ocr_data["raw_text"])
                # Pattern: "6 Monatsraten" or "6 Raten" or "Ratenanzahl: 6"
                m_count = re.search(r'(\d+)\s*(?:monats)?rate[n]?', raw, re.IGNORECASE)
                if m_count and not ratenanzahl:
                    ratenanzahl = int(m_count.group(1))
                # Pattern: "EUR 442,84" near "Rate" or "monatlich"
                m_amount = re.search(
                    r'(?:rate|monatlich)[^€\d]*(?:EUR\s*)?(\d[\d.,]*)',
                    raw, re.IGNORECASE,
                )
                if m_amount and not ratenbetrag:
                    ratenbetrag = normalize_amount(m_amount.group(1))

            if not ratenbetrag or ratenbetrag <= 0 or ratenanzahl <= 0:
                logger.warning("SVS Ratenzahlung: missing ratenanzahl=%s or ratenbetrag=%s", ratenanzahl, ratenbetrag)
                return

            start_date = normalize_date(ocr_data.get("date"))
            if not start_date:
                from datetime import date as date_cls
                start_date = date_cls.today()

            # Get user_id from document
            user_id = ocr_data.get("_user_id")
            if not user_id:
                logger.warning("SVS Ratenzahlung: no user_id available")
                return

            from app.models.recurring_transaction import (
                RecurringTransaction,
                RecurringTransactionType,
                RecurrenceFrequency,
            )
            from dateutil.relativedelta import relativedelta

            end_date = start_date + relativedelta(months=ratenanzahl)

            recurring = RecurringTransaction(
                user_id=user_id,
                recurring_type=RecurringTransactionType.OTHER_EXPENSE,
                description=f"SVS Ratenzahlung ({ratenanzahl}x €{ratenbetrag:.2f})",
                amount=ratenbetrag,
                frequency=RecurrenceFrequency.MONTHLY,
                start_date=start_date,
                end_date=end_date,
                template="svs_ratenzahlung",
                is_active=True,
            )
            self.db.add(recurring)
            self.db.flush()
            logger.info(
                "Created SVS Ratenzahlung recurring: %dx €%.2f, %s to %s",
                ratenanzahl, ratenbetrag, start_date, end_date,
            )
        except Exception as e:
            logger.warning("Failed to create SVS Ratenzahlung recurring: %s", e)

    def _extract_from_kirchenbeitrag(self, ocr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction from Kirchenbeitrag (church tax) confirmation.

        Always expense / Sonderausgaben. Cap: €600 (2024+) / €400 (before 2024).
        Goes into E1 KZ 458.
        """
        amount = ocr_data.get("amount") or ocr_data.get("beitrag") or ocr_data.get("betrag")
        if not amount:
            return None
        normalized_amount = normalize_amount(amount)
        if normalized_amount is None:
            return None

        date = ocr_data.get("date")
        normalized_date = normalize_date(date)
        tax_year = ocr_data.get("tax_year")

        parish = (
            ocr_data.get("merchant")
            or ocr_data.get("issuer")
            or ocr_data.get("pfarre")
            or ocr_data.get("kirchengemeinde")
            or "Kirchenbeitrag"
        )
        desc = f"Kirchenbeitrag {tax_year}" if tax_year else f"Kirchenbeitrag — {parish}"

        return {
            "amount": normalized_amount,
            "date": normalized_date or date,
            "description": desc,
            "_kirchenbeitrag": True,
        }

    def _extract_from_spendenbestaetigung(self, ocr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction from Spendenbestätigung (donation confirmation).

        Always expense / Sonderausgaben. Cap: 10% of total income.
        Only for §4a EStG registered organisations (SO-Nummer).
        Goes into E1 KZ 451.
        Note: from 2024 most donations are auto-reported to Finanzamt
        (automatische Datenübermittlung).
        """
        amount = ocr_data.get("amount") or ocr_data.get("spendenbetrag") or ocr_data.get("betrag")
        if not amount:
            return None
        normalized_amount = normalize_amount(amount)
        if normalized_amount is None:
            return None

        date = ocr_data.get("date")
        normalized_date = normalize_date(date)
        tax_year = ocr_data.get("tax_year")

        org = (
            ocr_data.get("merchant")
            or ocr_data.get("issuer")
            or ocr_data.get("organisation")
            or ocr_data.get("verein")
            or "Spende"
        )
        so_nummer = ocr_data.get("so_nummer") or ocr_data.get("registrierungsnummer")
        desc = f"Spende — {org}"
        if so_nummer:
            desc += f" (SO {so_nummer})"
        if tax_year:
            desc = f"Spende {tax_year} — {org}"

        return {
            "amount": normalized_amount,
            "date": normalized_date or date,
            "description": desc,
            "_spendenbestaetigung": True,
            "_so_nummer": so_nummer,
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
            # SVS sub-type aware classification
            svs_sub = transaction_data.get("_svs_subtype", "vorschreibung")
            beitragsjahr = transaction_data.get("_beitragsjahr", "")

            if svs_sub == "gutschrift":
                reason = "SVS Gutschrift — Betriebseinnahme im Zufluss-Jahr (Zufluss-Abfluss-Prinzip)"
                if beitragsjahr:
                    reason += f" | Beitragsjahr: {beitragsjahr}"
                return {
                    "transaction_type": TransactionType.INCOME.value,
                    "category": ExpenseCategory.INSURANCE.value,  # Offsets SVS expense line
                    "is_deductible": False,
                    "deduction_reason": reason,
                    "confidence": 0.95,
                }

            if svs_sub == "saeumniszuschlag":
                return {
                    "transaction_type": TransactionType.EXPENSE.value,
                    "category": ExpenseCategory.OTHER.value,
                    "is_deductible": False,
                    "deduction_reason": "SVS Säumniszuschlag — NICHT als Betriebsausgabe absetzbar",
                    "confidence": 0.95,
                }

            if svs_sub == "nachforderung":
                reason = "SVS Nachbemessung Nachforderung — Betriebsausgabe im Zahlungsjahr (Zufluss-Abfluss-Prinzip, E1a KZ 9225)"
                if beitragsjahr:
                    reason += f" | Beitragsjahr: {beitragsjahr}"
                return {
                    "transaction_type": TransactionType.EXPENSE.value,
                    "category": ExpenseCategory.INSURANCE.value,
                    "is_deductible": True,
                    "deduction_reason": reason,
                    "confidence": 0.95,
                }

            # Default: vorschreibung (regular quarterly)
            return {
                "transaction_type": TransactionType.EXPENSE.value,
                "category": ExpenseCategory.INSURANCE.value,
                "is_deductible": True,
                "deduction_reason": "SVS Pflichtbeiträge — Betriebsausgabe (E1a KZ 9225)",
                "confidence": 0.95,
            }

        elif doc_type == DocumentType.KIRCHENBEITRAG.value:
            return {
                "transaction_type": TransactionType.EXPENSE.value,
                "category": ExpenseCategory.OTHER.value,
                "is_deductible": True,
                "deduction_reason": "Kirchenbeitrag — Sonderausgaben gem. §18 Abs.1 Z5 EStG (E1 KZ 458, max €600 ab 2024)",
                "confidence": 0.95,
            }

        elif doc_type == DocumentType.SPENDENBESTAETIGUNG.value:
            so_nummer = transaction_data.get("_so_nummer")
            reason = "Spende — Sonderausgaben gem. §4a EStG (E1 KZ 451, max 10% der Einkünfte)"
            if so_nummer:
                reason += f" | SO-Nr: {so_nummer}"
            else:
                reason += " | Hinweis: Ab 2024 werden die meisten Spenden automatisch ans Finanzamt gemeldet."
            return {
                "transaction_type": TransactionType.EXPENSE.value,
                "category": ExpenseCategory.OTHER.value,
                "is_deductible": True,
                "deduction_reason": reason,
                "confidence": 0.95,
            }

        elif doc_type == DocumentType.FORTBILDUNGSKOSTEN.value:
            return {
                "transaction_type": TransactionType.EXPENSE.value,
                "category": ExpenseCategory.EDUCATION.value,
                "is_deductible": True,
                "deduction_reason": "Fortbildungskosten — Werbungskosten (L1 KZ 720) oder Betriebsausgaben (E1a KZ 9230)",
                "confidence": 0.90,
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



