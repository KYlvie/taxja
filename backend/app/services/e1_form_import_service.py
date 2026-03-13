"""
Service for importing E1 Form (Einkommensteuererklärung) data into the system.

Takes structured E1FormData and creates:
1. Income transactions from KZ codes (245, 210, 220, 350, etc.)
2. Expense/deduction transactions (260, 261, 263, 450, 458, etc.)
3. Updates user profile with extracted info
4. Suggests property linking for rental income (KZ 350)
"""
from datetime import date
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User
from app.models.loss_carryforward import LossCarryforward
from app.services.e1_form_extractor import E1FormData, E1FormExtractor
from app.services.address_matcher import AddressMatcher

logger = logging.getLogger(__name__)


class E1FormImportService:
    """Import E1 tax declaration form data into the system"""
    
    def __init__(self, db: Session):
        self.db = db
        self.extractor = E1FormExtractor()
        self.address_matcher = AddressMatcher(db)
    
    def import_from_ocr_text(
        self, text: str, user_id: int, document_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract and import data from OCR text of an E1 form.
        
        Returns summary of imported data.
        """
        data = self.extractor.extract(text)
        return self.import_e1_data(data, user_id, document_id)
    
    def import_e1_data(
        self, data: E1FormData, user_id: int, document_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Import structured E1FormData into the system"""
        tax_year = data.tax_year or date.today().year - 1
        ref_date = date(tax_year, 12, 31)
        
        created_transactions: List[Dict[str, Any]] = []
        rental_income_transaction_id: Optional[int] = None
        
        # 1. Employment income (KZ 245)
        if data.kz_245 and data.kz_245 > 0:
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=TransactionType.INCOME,
                amount=data.kz_245,
                txn_date=ref_date,
                description=f"Einkünfte aus nichtselbständiger Arbeit {tax_year} (KZ 245)",
                income_category=IncomeCategory.EMPLOYMENT,
                document_id=document_id,
                source="e1_import",
            )
            created_transactions.append({
                "id": txn.id,
                "type": "income",
                "category": "employment",
                "amount": float(txn.amount),
                "description": txn.description,
                "kz": "245",
            })
        
        # 2. Self-employment income (KZ 210)
        if data.kz_210 and data.kz_210 != Decimal("0"):
            amount = abs(data.kz_210)
            txn_type = TransactionType.INCOME if data.kz_210 > 0 else TransactionType.EXPENSE
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=txn_type,
                amount=amount,
                txn_date=ref_date,
                description=f"Einkünfte aus selbständiger Arbeit {tax_year} (KZ 210)",
                income_category=IncomeCategory.SELF_EMPLOYMENT if data.kz_210 > 0 else None,
                expense_category=ExpenseCategory.OTHER if data.kz_210 < 0 else None,
                document_id=document_id,
                source="e1_import",
                is_deductible=data.kz_210 < 0,
            )
            created_transactions.append({
                "id": txn.id,
                "type": txn_type.value,
                "category": "self_employment",
                "amount": float(amount),
                "description": txn.description,
                "kz": "210",
            })
        
        # 3. Business income (KZ 220)
        if data.kz_220 and data.kz_220 != Decimal("0"):
            amount = abs(data.kz_220)
            txn_type = TransactionType.INCOME if data.kz_220 > 0 else TransactionType.EXPENSE
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=txn_type,
                amount=amount,
                txn_date=ref_date,
                description=f"Einkünfte aus Gewerbebetrieb {tax_year} (KZ 220)",
                income_category=IncomeCategory.BUSINESS if data.kz_220 > 0 else None,
                expense_category=ExpenseCategory.OTHER if data.kz_220 < 0 else None,
                document_id=document_id,
                source="e1_import",
                is_deductible=data.kz_220 < 0,
            )
            created_transactions.append({
                "id": txn.id,
                "type": txn_type.value,
                "category": "business",
                "amount": float(amount),
                "description": txn.description,
                "kz": "220",
            })
        
        # 4. Rental income (KZ 350) - with detailed breakdown if available
        rental_income_transaction_id = None
        if data.kz_350 and data.kz_350 != Decimal("0"):
            amount = abs(data.kz_350)
            txn_type = TransactionType.INCOME if data.kz_350 > 0 else TransactionType.EXPENSE
            
            # Check if we have detailed rental breakdown
            if data.vermietung_details:
                # Create detailed transactions for each rental property component
                for prop_detail in data.vermietung_details:
                    # Rental income
                    if prop_detail.einnahmen and prop_detail.einnahmen > 0:
                        txn = self._create_transaction(
                            user_id=user_id,
                            txn_type=TransactionType.INCOME,
                            amount=prop_detail.einnahmen,
                            txn_date=ref_date,
                            description=f"Mieteinnahmen {tax_year} - {prop_detail.address or prop_detail.city or 'Immobilie'} (KZ 9460)",
                            income_category=IncomeCategory.RENTAL,
                            document_id=document_id,
                            source="e1_import",
                        )
                        created_transactions.append({
                            "id": txn.id,
                            "type": "income",
                            "category": "rental_income",
                            "amount": float(txn.amount),
                            "description": txn.description,
                            "kz": "9460",
                        })
                    
                    # Rental expenses
                    rental_expenses = [
                        (prop_detail.afa, "AfA (Abschreibung)", "9500", ExpenseCategory.DEPRECIATION_AFA),
                        (prop_detail.fremdfinanzierung, "Fremdfinanzierungskosten", "9510", ExpenseCategory.LOAN_INTEREST),
                        (prop_detail.instandhaltung, "Instandhaltungskosten", "9520", ExpenseCategory.MAINTENANCE),
                        (prop_detail.uebrige_werbungskosten, "Übrige Werbungskosten", "9530", ExpenseCategory.OTHER),
                    ]
                    
                    for exp_amount, exp_desc, exp_kz, exp_category in rental_expenses:
                        if exp_amount and exp_amount > 0:
                            txn = self._create_transaction(
                                user_id=user_id,
                                txn_type=TransactionType.EXPENSE,
                                amount=exp_amount,
                                txn_date=ref_date,
                                description=f"{exp_desc} {tax_year} - {prop_detail.address or prop_detail.city or 'Immobilie'} (KZ {exp_kz})",
                                expense_category=exp_category,
                                document_id=document_id,
                                source="e1_import",
                                is_deductible=True,
                            )
                            created_transactions.append({
                                "id": txn.id,
                                "type": "expense",
                                "category": exp_category.value,
                                "amount": float(txn.amount),
                                "description": txn.description,
                                "kz": exp_kz,
                            })
            else:
                # No detailed breakdown, create summary transaction
                txn = self._create_transaction(
                    user_id=user_id,
                    txn_type=txn_type,
                    amount=amount,
                    txn_date=ref_date,
                    description=f"Einkünfte aus Vermietung und Verpachtung {tax_year} (KZ 350)",
                    income_category=IncomeCategory.RENTAL if data.kz_350 > 0 else None,
                    expense_category=ExpenseCategory.MAINTENANCE if data.kz_350 < 0 else None,
                    document_id=document_id,
                    source="e1_import",
                    is_deductible=data.kz_350 < 0,
                )
                rental_income_transaction_id = txn.id
                created_transactions.append({
                    "id": txn.id,
                    "type": txn_type.value,
                    "category": "rental",
                    "amount": float(amount),
                    "description": txn.description,
                    "kz": "350",
                })
        
        # 5. Capital income (KZ 370)
        if data.kz_370 and data.kz_370 > 0:
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=TransactionType.INCOME,
                amount=data.kz_370,
                txn_date=ref_date,
                description=f"Einkünfte aus Kapitalvermögen {tax_year} (KZ 370)",
                income_category=IncomeCategory.CAPITAL_GAINS,
                document_id=document_id,
                source="e1_import",
            )
            created_transactions.append({
                "id": txn.id,
                "type": "income",
                "category": "capital",
                "amount": float(txn.amount),
                "description": txn.description,
                "kz": "370",
            })
        
        # 6. Other income (KZ 390)
        if data.kz_390 and data.kz_390 > 0:
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=TransactionType.INCOME,
                amount=data.kz_390,
                txn_date=ref_date,
                description=f"Sonstige Einkünfte {tax_year} (KZ 390)",
                income_category=IncomeCategory.OTHER,
                document_id=document_id,
                source="e1_import",
            )
            created_transactions.append({
                "id": txn.id,
                "type": "income",
                "category": "other",
                "amount": float(txn.amount),
                "description": txn.description,
                "kz": "390",
            })
        
        # 7. Werbungskosten (KZ 260) - only if no detailed breakdown
        if data.kz_260 and data.kz_260 > 0:
            # Check if we have detailed Werbungskosten
            has_detailed = any([
                data.gewerkschaftsbeitraege,
                data.arbeitsmittel,
                data.fachliteratur,
                data.reisekosten,
                data.fortbildung,
                data.familienheimfahrten,
                data.doppelte_haushaltsfuehrung,
                data.sonstige_werbungskosten
            ])
            
            if not has_detailed:
                txn = self._create_transaction(
                    user_id=user_id,
                    txn_type=TransactionType.EXPENSE,
                    amount=data.kz_260,
                    txn_date=ref_date,
                    description=f"Werbungskosten {tax_year} (KZ 260)",
                    expense_category=ExpenseCategory.OTHER,
                    document_id=document_id,
                    source="e1_import",
                    is_deductible=True,
                )
                created_transactions.append({
                    "id": txn.id,
                    "type": "expense",
                    "category": "werbungskosten",
                    "amount": float(txn.amount),
                    "description": txn.description,
                    "kz": "260",
                })
        
        # 7a. Detailed Werbungskosten breakdown
        werbungskosten_items = [
            (data.gewerkschaftsbeitraege, "Gewerkschaftsbeiträge", "717", ExpenseCategory.OTHER),
            (data.arbeitsmittel, "Arbeitsmittel", "719", ExpenseCategory.OFFICE_SUPPLIES),
            (data.fachliteratur, "Fachliteratur", "720", ExpenseCategory.OFFICE_SUPPLIES),
            (data.reisekosten, "Beruflich veranlasste Reisekosten", "721", ExpenseCategory.TRAVEL),
            (data.fortbildung, "Fortbildungskosten", "722", ExpenseCategory.PROFESSIONAL_SERVICES),
            (data.familienheimfahrten, "Familienheimfahrten", "300", ExpenseCategory.COMMUTING),
            (data.doppelte_haushaltsfuehrung, "Doppelte Haushaltsführung", "723", ExpenseCategory.OTHER),
            (data.sonstige_werbungskosten, "Sonstige Werbungskosten", "724", ExpenseCategory.OTHER),
        ]
        
        for amount, desc, kz, category in werbungskosten_items:
            if amount and amount > 0:
                txn = self._create_transaction(
                    user_id=user_id,
                    txn_type=TransactionType.EXPENSE,
                    amount=amount,
                    txn_date=ref_date,
                    description=f"{desc} {tax_year} (KZ {kz})",
                    expense_category=category,
                    document_id=document_id,
                    source="e1_import",
                    is_deductible=True,
                )
                created_transactions.append({
                    "id": txn.id,
                    "type": "expense",
                    "category": category.value,
                    "amount": float(txn.amount),
                    "description": txn.description,
                    "kz": kz,
                })
        
        # 8. Pendlerpauschale (KZ 261)
        if data.kz_261 and data.kz_261 > 0:
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=TransactionType.EXPENSE,
                amount=data.kz_261,
                txn_date=ref_date,
                description=f"Pendlerpauschale {tax_year} (KZ 261)",
                expense_category=ExpenseCategory.COMMUTE,
                document_id=document_id,
                source="e1_import",
                is_deductible=True,
            )
            created_transactions.append({
                "id": txn.id,
                "type": "expense",
                "category": "commute",
                "amount": float(txn.amount),
                "description": txn.description,
                "kz": "261",
            })
        
        # 9. Telearbeitspauschale (KZ 263)
        if data.kz_263 and data.kz_263 > 0:
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=TransactionType.EXPENSE,
                amount=data.kz_263,
                txn_date=ref_date,
                description=f"Telearbeitspauschale {tax_year} (KZ 263)",
                expense_category=ExpenseCategory.HOME_OFFICE,
                document_id=document_id,
                source="e1_import",
                is_deductible=True,
            )
            created_transactions.append({
                "id": txn.id,
                "type": "expense",
                "category": "home_office",
                "amount": float(txn.amount),
                "description": txn.description,
                "kz": "263",
            })
        
        # 10. Sonderausgaben (KZ 450)
        if data.kz_450 and data.kz_450 > 0:
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=TransactionType.EXPENSE,
                amount=data.kz_450,
                txn_date=ref_date,
                description=f"Sonderausgaben {tax_year} (KZ 450)",
                expense_category=ExpenseCategory.OTHER,
                document_id=document_id,
                source="e1_import",
                is_deductible=True,
            )
            created_transactions.append({
                "id": txn.id,
                "type": "expense",
                "category": "sonderausgaben",
                "amount": float(txn.amount),
                "description": txn.description,
                "kz": "450",
            })
        
        # 11. Kirchenbeitrag (KZ 458)
        if data.kz_458 and data.kz_458 > 0:
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=TransactionType.EXPENSE,
                amount=data.kz_458,
                txn_date=ref_date,
                description=f"Kirchenbeitrag {tax_year} (KZ 458)",
                expense_category=ExpenseCategory.DONATIONS,
                document_id=document_id,
                source="e1_import",
                is_deductible=True,
            )
            created_transactions.append({
                "id": txn.id,
                "type": "expense",
                "category": "church",
                "amount": float(txn.amount),
                "description": txn.description,
                "kz": "458",
            })
        
        # 12. Spenden (KZ 459)
        if data.kz_459 and data.kz_459 > 0:
            txn = self._create_transaction(
                user_id=user_id,
                txn_type=TransactionType.EXPENSE,
                amount=data.kz_459,
                txn_date=ref_date,
                description=f"Spenden {tax_year} (KZ 459)",
                expense_category=ExpenseCategory.DONATIONS,
                document_id=document_id,
                source="e1_import",
                is_deductible=True,
            )
            created_transactions.append({
                "id": txn.id,
                "type": "expense",
                "category": "donations",
                "amount": float(txn.amount),
                "description": txn.description,
                "kz": "459",
            })
        
        # Update user profile
        self._update_user_profile(user_id, data)
        
        # Process loss carryforward data
        loss_carryforward_info = self._process_loss_carryforward(user_id, tax_year, data)
        
        e1_summary = self.extractor.to_dict(data)
        
        # Generate property linking suggestions if rental income detected
        property_linking_suggestions = []
        requires_property_linking = False
        
        if rental_income_transaction_id is not None:
            requires_property_linking = True
            property_linking_suggestions = self._generate_property_suggestions(
                user_id=user_id,
                transaction_id=rental_income_transaction_id,
                address_hint=None  # E1 forms typically don't include property addresses
            )
        
        return {
            "tax_year": tax_year,
            "taxpayer_name": data.taxpayer_name,
            "steuernummer": data.steuernummer,
            "transactions_created": len(created_transactions),
            "transactions": created_transactions,
            "confidence": data.confidence,
            "e1_data": e1_summary,
            "all_kz_values": {k: float(v) for k, v in data.all_kz_values.items()},
            "requires_property_linking": requires_property_linking,
            "property_linking_suggestions": property_linking_suggestions,
            "tax_calculation": e1_summary.get("tax_calculation"),
            "rental_details": e1_summary.get("vermietung_details", []),
            "loss_carryforward": loss_carryforward_info,
            "employment_details": {
                "anzahl_arbeitgeber": data.anzahl_arbeitgeber,
                "detailed_expenses": {
                    "gewerkschaftsbeitraege": float(data.gewerkschaftsbeitraege) if data.gewerkschaftsbeitraege else None,
                    "arbeitsmittel": float(data.arbeitsmittel) if data.arbeitsmittel else None,
                    "fachliteratur": float(data.fachliteratur) if data.fachliteratur else None,
                    "reisekosten": float(data.reisekosten) if data.reisekosten else None,
                    "fortbildung": float(data.fortbildung) if data.fortbildung else None,
                    "familienheimfahrten": float(data.familienheimfahrten) if data.familienheimfahrten else None,
                    "doppelte_haushaltsfuehrung": float(data.doppelte_haushaltsfuehrung) if data.doppelte_haushaltsfuehrung else None,
                    "sonstige_werbungskosten": float(data.sonstige_werbungskosten) if data.sonstige_werbungskosten else None,
                }
            }
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
        source: str = "e1_import",
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
    
    def _generate_property_suggestions(
        self,
        user_id: int,
        transaction_id: int,
        address_hint: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate property linking suggestions for a rental income transaction.
        
        Args:
            user_id: User ID
            transaction_id: Transaction ID to link
            address_hint: Optional address string from E1 data (rarely available)
        
        Returns:
            List of property suggestions with confidence scores
        """
        suggestions = []
        
        # If address hint is available, use AddressMatcher
        if address_hint:
            matches = self.address_matcher.match_address(address_hint, user_id)
            
            for match in matches:
                suggestions.append({
                    "property_id": str(match.property.id),
                    "address": match.property.address,
                    "street": match.property.street,
                    "city": match.property.city,
                    "postal_code": match.property.postal_code,
                    "confidence": match.confidence,
                    "matched_components": match.matched_components,
                    "suggested_action": self._determine_action(match.confidence),
                })
        else:
            # No address hint - return all active properties for user selection
            from app.models.property import Property, PropertyStatus
            
            properties = self.db.query(Property).filter(
                Property.user_id == user_id,
                Property.status == PropertyStatus.ACTIVE
            ).all()
            
            for prop in properties:
                suggestions.append({
                    "property_id": str(prop.id),
                    "address": prop.address,
                    "street": prop.street,
                    "city": prop.city,
                    "postal_code": prop.postal_code,
                    "confidence": 0.0,  # No matching performed
                    "matched_components": {},
                    "suggested_action": "manual_select",
                })
        
        return suggestions
    
    def _determine_action(self, confidence: float) -> str:
        """
        Determine suggested action based on confidence score.
        
        Returns:
            - "auto_link": High confidence (>0.9) - suggest automatic linking
            - "suggest": Medium confidence (0.7-0.9) - show as option
            - "manual_select": Low confidence (<0.7) - user must choose
        """
        if confidence > 0.9:
            return "auto_link"
        elif confidence >= 0.7:
            return "suggest"
        else:
            return "manual_select"
    
    def link_imported_rental_income(
        self,
        transaction_id: int,
        property_id: UUID,
        user_id: int
    ) -> Transaction:
        """
        Link an imported rental income transaction to a property.
        
        Args:
            transaction_id: Transaction ID to link
            property_id: Property ID to link to
            user_id: User ID for ownership validation
        
        Returns:
            Updated transaction
        
        Raises:
            ValueError: If transaction or property not found, or ownership mismatch
        """
        from app.models.property import Property
        
        # Get transaction and validate ownership
        transaction = self.db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id
        ).first()
        
        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found or does not belong to user")
        
        # Get property and validate ownership
        property = self.db.query(Property).filter(
            Property.id == property_id,
            Property.user_id == user_id
        ).first()
        
        if not property:
            raise ValueError(f"Property {property_id} not found or does not belong to user")
        
        # Link transaction to property
        transaction.property_id = property_id
        self.db.commit()
        self.db.refresh(transaction)
        
        logger.info(
            f"Linked transaction {transaction_id} to property {property_id} "
            f"for user {user_id}"
        )
        
        return transaction
    
    def _update_user_profile(self, user_id: int, data: E1FormData) -> None:
        """Update user profile with info from E1 form"""
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
    
    def _process_loss_carryforward(
        self, user_id: int, tax_year: int, data: E1FormData
    ) -> Dict[str, Any]:
        """
        Process loss carryforward data from E1 form.
        
        Creates or updates LossCarryforward records based on:
        - KZ 462: Prior year losses (opening balance)
        - KZ 332/346/372: Losses used this year
        - KZ 341/342/371: New losses generated this year
        
        Returns summary of loss carryforward status.
        """
        loss_info = {
            "prior_year_losses": None,
            "losses_used_this_year": None,
            "new_losses_this_year": None,
            "remaining_balance": None,
            "details": []
        }
        
        # KZ 462: Total prior year losses (opening balance)
        if data.kz_462 and data.kz_462 > 0:
            loss_info["prior_year_losses"] = float(data.kz_462)
        
        # Calculate total losses used this year
        losses_used = Decimal("0")
        if data.kz_332:  # Business losses used
            losses_used += data.kz_332
            loss_info["details"].append({
                "type": "business_loss_used",
                "kz": "332",
                "amount": float(data.kz_332),
                "description": "Verrechenbare Verluste - eigener Betrieb"
            })
        if data.kz_346:  # Investment losses used
            losses_used += data.kz_346
            loss_info["details"].append({
                "type": "investment_loss_used",
                "kz": "346",
                "amount": float(data.kz_346),
                "description": "Verrechenbare Verluste - Beteiligungen"
            })
        if data.kz_372:  # Non-business losses used
            losses_used += data.kz_372
            loss_info["details"].append({
                "type": "non_business_loss_used",
                "kz": "372",
                "amount": float(data.kz_372),
                "description": "Verrechenbare Verluste - außerbetrieblich"
            })
        
        if losses_used > 0:
            loss_info["losses_used_this_year"] = float(losses_used)
        
        # Calculate new losses generated this year
        new_losses = Decimal("0")
        if data.kz_341:  # New business losses
            new_losses += data.kz_341
            loss_info["details"].append({
                "type": "new_business_loss",
                "kz": "341",
                "amount": float(data.kz_341),
                "description": "Nicht ausgleichsfähige Verluste - eigener Betrieb"
            })
        if data.kz_342:  # New investment losses
            new_losses += data.kz_342
            loss_info["details"].append({
                "type": "new_investment_loss",
                "kz": "342",
                "amount": float(data.kz_342),
                "description": "Nicht ausgleichsfähige Verluste - Beteiligungen"
            })
        if data.kz_371:  # New non-business losses
            new_losses += data.kz_371
            loss_info["details"].append({
                "type": "new_non_business_loss",
                "kz": "371",
                "amount": float(data.kz_371),
                "description": "Nicht ausgleichsfähige Verluste - außerbetrieblich"
            })
        
        if new_losses > 0:
            loss_info["new_losses_this_year"] = float(new_losses)
            
            # Create LossCarryforward record for new losses
            # Check if record already exists for this year
            existing_loss = self.db.query(LossCarryforward).filter(
                LossCarryforward.user_id == user_id,
                LossCarryforward.loss_year == tax_year
            ).first()
            
            if existing_loss:
                # Update existing record
                existing_loss.loss_amount = new_losses
                existing_loss.remaining_amount = new_losses
                existing_loss.used_amount = Decimal("0")
                logger.info(f"Updated loss carryforward for user {user_id}, year {tax_year}: €{new_losses}")
            else:
                # Create new record
                new_loss_record = LossCarryforward(
                    user_id=user_id,
                    loss_year=tax_year,
                    loss_amount=new_losses,
                    used_amount=Decimal("0"),
                    remaining_amount=new_losses
                )
                self.db.add(new_loss_record)
                logger.info(f"Created loss carryforward for user {user_id}, year {tax_year}: €{new_losses}")
            
            self.db.commit()
        
        # Calculate remaining balance
        # Remaining = Prior losses - Losses used + New losses
        if data.kz_462:
            remaining = data.kz_462 - losses_used + new_losses
            loss_info["remaining_balance"] = float(remaining)
        elif new_losses > 0:
            loss_info["remaining_balance"] = float(new_losses)
        
        return loss_info
