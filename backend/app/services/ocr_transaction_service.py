"""Service for creating transaction suggestions from OCR data"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
import logging

from app.models.document import Document, DocumentType
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.services.transaction_classifier import TransactionClassifier
from app.services.deductibility_checker import DeductibilityChecker

logger = logging.getLogger(__name__)


class OCRTransactionService:
    """Service for creating transaction suggestions from OCR results"""

    def __init__(self, db: Session):
        self.db = db
        self.classifier = TransactionClassifier()
        self.deductibility_checker = DeductibilityChecker()

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
        line_items = ocr_data.get("line_items", [])

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
        """
        Create an actual transaction from a suggestion
        
        Args:
            suggestion: Transaction suggestion dictionary
            user_id: User ID
            
        Returns:
            Created transaction
        """
        # Parse transaction type
        transaction_type = TransactionType(suggestion["transaction_type"])
        
        # Parse category
        if transaction_type == TransactionType.INCOME:
            category = IncomeCategory(suggestion["category"]) if suggestion["category"] else None
        else:
            category = ExpenseCategory(suggestion["category"]) if suggestion["category"] else None
        
        # Parse date
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

        # Create transaction
        transaction = Transaction(
            user_id=user_id,
            type=transaction_type,
            amount=Decimal(suggestion["amount"]),
            transaction_date=txn_date,
            description=suggestion["description"],
            income_category=category if transaction_type == TransactionType.INCOME else None,
            expense_category=category if transaction_type == TransactionType.EXPENSE else None,
            is_deductible=suggestion.get("is_deductible", False),
            document_id=suggestion["document_id"],
            import_source="ocr",
            classification_confidence=Decimal(str(suggestion.get("confidence", 0.5))),
            needs_review=suggestion.get("needs_review", True),
        )
        
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        
        # Update document with transaction link
        document = self.db.query(Document).filter(Document.id == suggestion["document_id"]).first()
        if document:
            document.transaction_id = transaction.id
            self.db.commit()
        
        logger.info(f"Created transaction {transaction.id} from OCR document {suggestion['document_id']}")
        
        return transaction

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

        if not amount:
            return None

        if product_summary:
            description = f"{merchant}: {product_summary}"
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
                
                if category:
                    user_type_val = user.user_type.value if hasattr(user.user_type, 'value') else str(user.user_type or "employee")
                    # Pass OCR data + description so AI can analyze ambiguous cases
                    ocr_data = document.ocr_result if document.ocr_result else {}
                    deduct_result = self.deductibility_checker.check(
                        category, user_type_val,
                        ocr_data=ocr_data,
                        description=description,
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



