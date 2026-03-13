"""
Service for importing Einkommensteuerbescheid data into the system.

Takes structured BescheidData and creates:
1. Income transactions (employment, rental, etc.)
2. Expense transactions (deductions)
3. Updates user profile with extracted info (children, tax number)
4. Suggests property linking for rental income (vermietung_details)
"""
from datetime import date
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import logging

from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.document import Document, DocumentType
from app.models.user import User
from app.services.bescheid_extractor import BescheidData, BescheidExtractor
from app.services.address_matcher import AddressMatcher

logger = logging.getLogger(__name__)


class BescheidImportService:
    """Import Einkommensteuerbescheid data into the system"""

    def __init__(self, db: Session):
        self.db = db
        self.extractor = BescheidExtractor()
        self.address_matcher = AddressMatcher(db)

    def import_from_ocr_text(
        self, text: str, user_id: int, document_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract and import data from OCR text of a Steuerberechnung.

        Returns summary of imported data.
        """
        data = self.extractor.extract(text)
        return self.import_bescheid_data(data, user_id, document_id)

    def import_bescheid_data(
        self, data: BescheidData, user_id: int, document_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Import structured BescheidData into the system"""
        tax_year = data.tax_year or date.today().year - 1
        ref_date = date(tax_year, 12, 31)

        created_transactions: List[Dict[str, Any]] = []
        property_linking_suggestions: List[Dict[str, Any]] = []

        # 1. Employment income
        if data.einkuenfte_nichtselbstaendig and data.einkuenfte_nichtselbstaendig > 0:
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=TransactionType.INCOME,
                amount=data.einkuenfte_nichtselbstaendig,
                txn_date=ref_date,
                description=f"Einkünfte aus nichtselbständiger Arbeit {tax_year}"
                + (f" - {data.employer_name}" if data.employer_name else ""),
                income_category=IncomeCategory.EMPLOYMENT,
                document_id=document_id,
                source="bescheid_import",
            )
            created_transactions.append({
                "id": txn.id,
                "type": "income",
                "category": "employment",
                "amount": float(txn.amount),
                "description": txn.description,
            })

        # 2. Rental income (V+V) - individual properties
        if data.vermietung_details:
            for detail in data.vermietung_details:
                amount = detail["amount"]
                address = detail.get("address", "")
                if amount == Decimal("0"):
                    continue
                txn_type = TransactionType.INCOME if amount > 0 else TransactionType.EXPENSE
                cat_income = IncomeCategory.RENTAL if amount > 0 else None
                cat_expense = ExpenseCategory.MAINTENANCE if amount < 0 else None
                txn = self._create_transaction(
                    user_id=user_id,
                    txn_type=txn_type,
                    amount=abs(amount),
                    txn_date=ref_date,
                    description=f"V+V {tax_year}: {address}" if address else f"V+V {tax_year}",
                    income_category=cat_income,
                    expense_category=cat_expense,
                    document_id=document_id,
                    source="bescheid_import",
                    is_deductible=amount < 0,
                )
                created_transactions.append({
                    "id": txn.id,
                    "type": txn_type.value,
                    "category": "rental",
                    "amount": float(abs(amount)),
                    "description": txn.description,
                })
                
                # Attempt property matching if address is available
                if address:
                    suggestion = self._generate_property_linking_suggestion(
                        transaction_id=txn.id,
                        address=address,
                        user_id=user_id
                    )
                    if suggestion:
                        property_linking_suggestions.append(suggestion)
        elif data.einkuenfte_vermietung and data.einkuenfte_vermietung != Decimal("0"):
            amount = data.einkuenfte_vermietung
            txn_type = TransactionType.INCOME if amount > 0 else TransactionType.EXPENSE
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=txn_type,
                amount=abs(amount),
                txn_date=ref_date,
                description=f"Einkünfte aus Vermietung und Verpachtung {tax_year}",
                income_category=IncomeCategory.RENTAL if amount > 0 else None,
                expense_category=ExpenseCategory.MAINTENANCE if amount < 0 else None,
                document_id=document_id,
                source="bescheid_import",
                is_deductible=amount < 0,
            )
            created_transactions.append({
                "id": txn.id,
                "type": txn_type.value,
                "category": "rental",
                "amount": float(abs(amount)),
                "description": txn.description,
            })

        # 3. Werbungskosten (if beyond Pauschale)
        if data.werbungskosten_pauschale and data.werbungskosten_pauschale > Decimal("132"):
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=TransactionType.EXPENSE,
                amount=data.werbungskosten_pauschale,
                txn_date=ref_date,
                description=f"Werbungskosten {tax_year}",
                expense_category=ExpenseCategory.OTHER,
                document_id=document_id,
                source="bescheid_import",
                is_deductible=True,
            )
            created_transactions.append({
                "id": txn.id,
                "type": "expense",
                "category": "werbungskosten",
                "amount": float(txn.amount),
                "description": txn.description,
            })

        # 4. Telearbeitspauschale
        if data.telearbeitspauschale and data.telearbeitspauschale > 0:
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=TransactionType.EXPENSE,
                amount=data.telearbeitspauschale,
                txn_date=ref_date,
                description=f"Telearbeitspauschale {tax_year}",
                expense_category=ExpenseCategory.HOME_OFFICE,
                document_id=document_id,
                source="bescheid_import",
                is_deductible=True,
            )
            created_transactions.append({
                "id": txn.id,
                "type": "expense",
                "category": "home_office",
                "amount": float(txn.amount),
                "description": txn.description,
            })

        # 5. Update user profile if we have useful info
        self._update_user_profile(user_id, data)

        # 6. Update document type if linked
        if document_id:
            doc = self.db.query(Document).filter(Document.id == document_id).first()
            if doc:
                try:
                    doc.document_type = DocumentType.EINKOMMENSTEUERBESCHEID
                    self.db.commit()
                except Exception:
                    # Enum value may not exist in DB yet (needs migration)
                    self.db.rollback()

        bescheid_summary = self.extractor.to_dict(data)

        return {
            "tax_year": tax_year,
            "taxpayer_name": data.taxpayer_name,
            "steuernummer": data.steuernummer,
            "finanzamt": data.finanzamt,
            "einkommen": float(data.einkommen) if data.einkommen else None,
            "festgesetzte_einkommensteuer": (
                float(data.festgesetzte_einkommensteuer)
                if data.festgesetzte_einkommensteuer
                else None
            ),
            "abgabengutschrift": (
                float(data.abgabengutschrift) if data.abgabengutschrift else None
            ),
            "abgabennachforderung": (
                float(data.abgabennachforderung) if data.abgabennachforderung else None
            ),
            "transactions_created": len(created_transactions),
            "transactions": created_transactions,
            "property_linking_suggestions": property_linking_suggestions,
            "requires_property_linking": len(property_linking_suggestions) > 0,
            "confidence": data.confidence,
            "bescheid_data": bescheid_summary,
        }

    def _create_transaction(
        self,
        user_id: int,
        txn_type: TransactionType,
        amount: Decimal,
        txn_date: date,
        description: str,
        income_category: Optional[IncomeCategory] = None,
        expense_category: Optional[ExpenseCategory] = None,
        document_id: Optional[int] = None,
        source: str = "bescheid_import",
        is_deductible: bool = False,
    ) -> Transaction:
        txn = Transaction(
            user_id=user_id,
            type=txn_type,
            amount=amount,
            transaction_date=txn_date,
            description=description,
            income_category=income_category,
            expense_category=expense_category,
            document_id=document_id,
            import_source=source,
            is_deductible=is_deductible,
            classification_confidence=Decimal("0.95"),
            needs_review=False,
        )
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        return txn

    def _update_user_profile(self, user_id: int, data: BescheidData) -> None:
        """Update user profile with info from Bescheid"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return

        changed = False

        # Update tax number if not set
        if data.steuernummer and not user.tax_number:
            user.tax_number = data.steuernummer
            changed = True

        # Update family info
        if data.anzahl_kinder is not None:
            family_info = user.family_info or {}
            if family_info.get("num_children") != data.anzahl_kinder:
                family_info["num_children"] = data.anzahl_kinder
                user.family_info = family_info
                changed = True

        if data.alleinerzieher is not None:
            family_info = user.family_info or {}
            if family_info.get("is_single_parent") != data.alleinerzieher:
                family_info["is_single_parent"] = data.alleinerzieher
                user.family_info = family_info
                changed = True

        if changed:
            self.db.commit()

    def _generate_property_linking_suggestion(
        self, transaction_id: int, address: str, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Generate property linking suggestion using AddressMatcher.
        
        Args:
            transaction_id: ID of the created transaction
            address: Extracted property address from Bescheid
            user_id: User ID for property matching
        
        Returns:
            Dictionary with linking suggestion or None if no matches found
        """
        try:
            # Use AddressMatcher to find matching properties
            matches = self.address_matcher.match_address(address, user_id)
            
            if not matches:
                # No matches found - suggest creating new property
                return {
                    "transaction_id": transaction_id,
                    "extracted_address": address,
                    "matched_property_id": None,
                    "confidence_score": 0.0,
                    "suggested_action": "create_new",
                    "match_details": None
                }
            
            # Get the best match
            best_match = matches[0]
            confidence = best_match.confidence
            
            # Determine suggested action based on confidence
            if confidence > 0.9:
                suggested_action = "auto_link"
            elif confidence >= 0.7:
                suggested_action = "suggest"
            else:
                suggested_action = "create_new"
            
            return {
                "transaction_id": transaction_id,
                "extracted_address": address,
                "matched_property_id": str(best_match.property.id),
                "matched_property_address": best_match.property.address,
                "confidence_score": round(confidence, 2),
                "suggested_action": suggested_action,
                "match_details": {
                    "street_match": best_match.matched_components.get("street", False),
                    "postal_code_match": best_match.matched_components.get("postal_code", False),
                    "city_match": best_match.matched_components.get("city", False)
                },
                "alternative_matches": [
                    {
                        "property_id": str(match.property.id),
                        "property_address": match.property.address,
                        "confidence_score": round(match.confidence, 2)
                    }
                    for match in matches[1:3]  # Include up to 2 alternative matches
                ] if len(matches) > 1 else []
            }
            
        except Exception as e:
            logger.error(f"Error generating property linking suggestion: {e}")
            return None
