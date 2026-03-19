"""Service for creating transaction suggestions from OCR data"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
import logging

from app.core.transaction_enum_coercion import (
    coerce_expense_category,
    coerce_income_category,
    coerce_transaction_type,
)
from app.models.document import Document, DocumentType
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.services.duplicate_detector import DuplicateDetector
from app.services.transaction_classifier import TransactionClassifier
from app.services.deductibility_checker import DeductibilityChecker

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
        self.deductibility_checker = DeductibilityChecker()
        self.duplicate_detector = DuplicateDetector(db)

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
        transaction_data = self._extract_transaction_data(document, ocr_data)

        if not transaction_data:
            logger.warning(f"Could not extract transaction data from document {document_id}")
            return []

        classification = self._classify_from_ocr(document, transaction_data, user_id)

        # Check if this is a NEEDS_AI category that might benefit from split analysis
        doc_type = str(document.document_type.value) if hasattr(document.document_type, 'value') else str(document.document_type)
        line_items = ocr_data.get("line_items") or ocr_data.get("items") or []

        if (
            doc_type in [DocumentType.RECEIPT.value, DocumentType.INVOICE.value]
            and line_items
            and len(line_items) >= 2
        ):
            from app.models.user import User
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                user_type_val = user.user_type.value if hasattr(user.user_type, 'value') else str(user.user_type or "employee")
                # Only attempt split for business user types
                if user_type_val in ("self_employed", "mixed", "gmbh"):
                    split = self.deductibility_checker.ai_split_analyze(
                        user_type_val, ocr_data, transaction_data.get("description", "")
                    )
                    if split and split.get("has_split"):
                        return self._build_split_suggestions(
                            document, transaction_data, classification, split, ocr_data
                        )

        # No split needed — return single suggestion
        suggestion = self._build_single_suggestion(
            document, transaction_data, classification, ocr_data
        )
        return [suggestion]

    def _build_single_suggestion(
        self, document, transaction_data, classification, ocr_data
    ) -> Dict[str, Any]:
        """Build a single transaction suggestion dict."""
        return {
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
            "extracted_fields": {k: (float(v) if isinstance(v, Decimal) else v.isoformat() if isinstance(v, (datetime,)) else v) for k, v in ocr_data.items()} if ocr_data else {},
        }

    def _build_split_suggestions(
        self, document, transaction_data, classification, split, ocr_data
    ) -> List[Dict[str, Any]]:
        """Build two suggestions from AI split analysis."""
        suggestions = []
        merchant = ocr_data.get("merchant", "")
        base_date = transaction_data["date"]
        date_str = base_date.isoformat() if base_date and hasattr(base_date, 'isoformat') else str(base_date) if base_date else None

        deduct_amt = Decimal(str(split["deductible_amount"]))
        non_deduct_amt = Decimal(str(split["non_deductible_amount"]))

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
            return [self._build_single_suggestion(document, transaction_data, classification, ocr_data)]

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
                "extracted_fields": {},
            })

        if not suggestions:
            return [self._build_single_suggestion(document, transaction_data, classification, ocr_data)]

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
        transaction_type, category, txn_date = self._parse_transaction_fields(suggestion)
        amount = Decimal(suggestion["amount"])
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
            if isinstance(raw_date, str):
                txn_date = datetime.fromisoformat(raw_date).date()
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
        )
        
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        
        # Update document with transaction link
        document = self.db.query(Document).filter(Document.id == suggestion["document_id"]).first()
        if document and not document.transaction_id:
            document.transaction_id = transaction.id
            self.db.commit()

        # Sync line items from document OCR data to transaction_line_items
        self._sync_line_items_from_document(transaction, suggestion)
        
        logger.info(f"Created transaction {transaction.id} from OCR document {suggestion['document_id']}")
        
        return transaction

    def _sync_line_items_from_document(
        self, transaction: Transaction, suggestion: Dict[str, Any]
    ) -> None:
        """Copy line items from OCR data into transaction_line_items table."""
        from app.models.transaction_line_item import TransactionLineItem

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
            for idx, li in enumerate(doc_line_items):
                desc = li.get("description") or li.get("name") or f"Item {idx + 1}"
                amt = (
                    li.get("amount") or li.get("total_price")
                    or li.get("total") or li.get("price")
                )
                if not amt:
                    continue
                vat_rate_raw = li.get("vat_rate")
                vat_rate = None
                if vat_rate_raw is not None:
                    vr = Decimal(str(vat_rate_raw))
                    vat_rate = vr / 100 if vr > 1 else vr
                item = TransactionLineItem(
                    transaction_id=transaction.id,
                    description=desc,
                    amount=Decimal(str(amt)),
                    quantity=li.get("quantity", 1),
                    category=li.get("category"),
                    is_deductible=li.get("is_deductible", transaction.is_deductible),
                    deduction_reason=li.get("deduction_reason"),
                    vat_rate=vat_rate,
                    vat_amount=Decimal(str(li["vat_amount"])) if li.get("vat_amount") else None,
                    classification_method=transaction.classification_method,
                    sort_order=idx,
                )
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

        return {
            "amount": Decimal(str(amount)),
            "date": date,
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

        return {
            "amount": Decimal(str(amount)),
            "date": date,
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
        
        return {
            "amount": Decimal(str(amount)),
            "date": date,
            "description": f"Salary from {employer}",
        }

    def _extract_from_lohnzettel(self, ocr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction data from Lohnzettel (wage tax card)"""
        gross_income = ocr_data.get("gross_income")
        date = ocr_data.get("date")
        employer = ocr_data.get("employer", "Employer")

        if not gross_income:
            return None

        return {
            "amount": Decimal(str(gross_income)),
            "date": date,
            "description": f"Salary from {employer}",
        }


    def _extract_from_svs_notice(self, ocr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction data from SVS contribution notice"""
        amount = ocr_data.get("amount") or ocr_data.get("contribution_amount")
        date = ocr_data.get("date")
        
        if not amount:
            return None
        
        return {
            "amount": Decimal(str(amount)),
            "date": date,
            "description": "SVS social insurance contribution",
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

        return {
            "amount": Decimal(str(einkommen)),
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

        return {
            "amount": Decimal(str(amount)),
            "date": date,
            "description": description,
        }

    def _classify_from_ocr(
        self, document: Document, transaction_data: Dict[str, Any], user_id: int
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
            transaction_type = TransactionType.EXPENSE
            
            from app.models.user import User
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if user:
                # Build a rich description for classification by combining
                # the transaction description with the raw text from the document
                raw_text = document.raw_text or ""
                description = transaction_data.get("description", "")
                # Combine description + first 500 chars of raw text for better matching
                combined_text = f"{description} {raw_text[:500]}"
                
                temp_transaction = Transaction(
                    user_id=user_id,
                    type=transaction_type,
                    amount=transaction_data["amount"],
                    transaction_date=transaction_data["date"] or datetime.utcnow().date(),
                    description=combined_text,
                )
                
                classification = self.classifier.classify_transaction(temp_transaction, user)
                category = classification.category if classification.category else None
                method = classification.method if hasattr(classification, 'method') else 'unknown'
                
                if category:
                    # If LLM already provided deductibility, use it directly
                    if method == 'llm' and hasattr(classification, 'is_deductible') and classification.is_deductible is not None:
                        is_deductible = classification.is_deductible
                        deduction_reason = getattr(classification, 'deduction_reason', '') or ''
                        deduct_requires_review = False
                    else:
                        user_type_val = user.user_type.value if hasattr(user.user_type, 'value') else str(user.user_type or "employee")
                        # Pass OCR data + description so AI can analyze ambiguous cases
                        ocr_data = document.ocr_result if document.ocr_result else {}
                        deduct_result = self.deductibility_checker.check(
                            category, user_type_val,
                            ocr_data=ocr_data,
                            description=description,
                            business_type=getattr(user, 'business_type', None),
                            business_industry=getattr(user, 'business_industry', None),
                        )
                        is_deductible = deduct_result.is_deductible
                        deduction_reason = deduct_result.reason
                        if deduct_result.tax_tip:
                            deduction_reason = f"{deduct_result.reason} | {deduct_result.tax_tip}"
                        deduct_requires_review = deduct_result.requires_review
                else:
                    is_deductible = False
                    deduction_reason = "Unable to determine deductibility"
                    deduct_requires_review = True
                confidence = classification.confidence
            else:
                category = None
                is_deductible = False
                deduction_reason = "Unable to determine deductibility"
                confidence = 0.5
                
            return {
                "transaction_type": transaction_type.value,
                "category": category,
                "is_deductible": is_deductible,
                "deduction_reason": deduction_reason,
                "confidence": confidence,
                "classification_method": method,
                "requires_review": deduct_requires_review,
            }
        else:
            return {
                "transaction_type": TransactionType.EXPENSE.value,
                "category": None,
                "is_deductible": False,
                "deduction_reason": "Unable to determine deductibility",
                "confidence": 0.3,
            }



