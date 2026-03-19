"""
Kaufvertrag Import Service

Imports property purchase contract data into the system, creating properties
and associated transactions for purchase costs and depreciation schedules.

This service:
1. Extracts data using KaufvertragExtractor
2. Creates or updates properties with deduplication using AddressMatcher
3. Creates purchase cost transactions (Grunderwerbsteuer, Eintragungsgebühr, Notarkosten)
4. Initializes historical depreciation schedules using HistoricalDepreciationService
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import date
from sqlalchemy.orm import Session

from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, ExpenseCategory
from app.services.kaufvertrag_extractor import KaufvertragExtractor, KaufvertragData
from app.services.address_matcher import AddressMatcher
from app.services.historical_depreciation_service import HistoricalDepreciationService


logger = logging.getLogger(__name__)


class KaufvertragImportService:
    """Import Kaufvertrag purchase contract data into the system."""

    def __init__(self, db: Session):
        """
        Initialize Kaufvertrag import service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.extractor = KaufvertragExtractor()
        self.address_matcher = AddressMatcher(db)
        self.depreciation_service = HistoricalDepreciationService(db)

    def import_from_ocr_text(
        self, text: str, user_id: int, document_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract and import Kaufvertrag data from OCR text.

        Args:
            text: OCR text from Kaufvertrag document
            user_id: ID of the user importing the data
            document_id: Optional document ID to link to property

        Returns:
            Dictionary with import results:
            {
                "property_id": UUID,
                "property_created": bool,
                "transactions_created": List[int],
                "depreciation_years": int,
                "extracted_data": Dict,
                "confidence": float
            }

        Raises:
            ValueError: If extraction fails or required fields are missing
        """
        # Extract data from OCR text
        logger.info(
            "Starting Kaufvertrag import",
            extra={"user_id": user_id, "document_id": document_id},
        )

        kaufvertrag_data = self.extractor.extract(text)

        # Validate required fields
        if not kaufvertrag_data.purchase_price:
            raise ValueError("Purchase price is required but not found in document")

        if not kaufvertrag_data.purchase_date:
            raise ValueError("Purchase date is required but not found in document")

        if not kaufvertrag_data.property_address:
            raise ValueError("Property address is required but not found in document")

        # Create or update property
        property_obj, property_created = self.create_or_update_property(
            kaufvertrag_data, user_id, document_id
        )

        # Create purchase cost transactions
        transactions = self.create_purchase_cost_transactions(
            kaufvertrag_data, user_id, property_obj.id
        )

        # Initialize depreciation schedule
        depreciation_years = 0
        effective_building_value = property_obj.building_value or kaufvertrag_data.building_value
        if effective_building_value and effective_building_value > 0:
            depreciation_result = self.initialize_depreciation_schedule(
                property_obj.id, effective_building_value, kaufvertrag_data.purchase_date
            )
            depreciation_years = depreciation_result["years_backfilled"]

        # Commit all changes
        self.db.commit()

        logger.info(
            "Kaufvertrag import completed",
            extra={
                "user_id": user_id,
                "property_id": str(property_obj.id),
                "property_created": property_created,
                "transactions_created": len(transactions),
                "depreciation_years": depreciation_years,
                "confidence": kaufvertrag_data.confidence,
            },
        )

        return {
            "property_id": property_obj.id,
            "property_created": property_created,
            "transactions_created": [t.id for t in transactions],
            "depreciation_years": depreciation_years,
            "extracted_data": self.extractor.to_dict(kaufvertrag_data),
            "confidence": kaufvertrag_data.confidence,
        }

    def create_or_update_property(
        self,
        kaufvertrag_data: KaufvertragData,
        user_id: int,
        document_id: Optional[int] = None,
    ) -> tuple[Property, bool]:
        """
        Create new property or update existing with acquisition details.

        Uses AddressMatcher for property deduplication. If a high-confidence
        match is found (>0.9), updates the existing property. Otherwise,
        creates a new property.

        Args:
            kaufvertrag_data: Extracted Kaufvertrag data
            user_id: ID of the user
            document_id: Optional document ID to link

        Returns:
            Tuple of (Property, created: bool)
        """
        # Try to find existing property using address matcher
        matches = self.address_matcher.match_address(
            kaufvertrag_data.property_address, user_id
        )

        # If high-confidence match found, update existing property
        if matches and matches[0].confidence > 0.9:
            property_obj = matches[0].property
            property_created = False

            logger.info(
                "Updating existing property from Kaufvertrag",
                extra={
                    "property_id": str(property_obj.id),
                    "match_confidence": matches[0].confidence,
                },
            )

            # Update purchase information if not already set
            if not property_obj.purchase_price or property_obj.purchase_price == 0:
                property_obj.purchase_price = kaufvertrag_data.purchase_price
                property_obj.purchase_date = kaufvertrag_data.purchase_date

            if not property_obj.building_value or property_obj.building_value == 0:
                if kaufvertrag_data.building_value:
                    property_obj.building_value = kaufvertrag_data.building_value
                else:
                    # Estimate 80% building, 20% land
                    property_obj.building_value = (
                        kaufvertrag_data.purchase_price * Decimal("0.8")
                    ).quantize(Decimal("0.01"))

            # Calculate land value
            property_obj.land_value = property_obj.purchase_price - property_obj.building_value

            # Update purchase costs if available
            if kaufvertrag_data.grunderwerbsteuer:
                property_obj.grunderwerbsteuer = kaufvertrag_data.grunderwerbsteuer
            if kaufvertrag_data.notary_fees:
                property_obj.notary_fees = kaufvertrag_data.notary_fees
            if kaufvertrag_data.registry_fees:
                property_obj.registry_fees = kaufvertrag_data.registry_fees

            # Update construction year if available
            if kaufvertrag_data.construction_year:
                property_obj.construction_year = kaufvertrag_data.construction_year

            # Link document if provided
            if document_id:
                property_obj.kaufvertrag_document_id = document_id

        else:
            # Create new property
            property_created = True

            # Determine building value
            if kaufvertrag_data.building_value:
                building_value = kaufvertrag_data.building_value
            else:
                # Estimate 80% building, 20% land
                building_value = (kaufvertrag_data.purchase_price * Decimal("0.8")).quantize(
                    Decimal("0.01")
                )

            # Calculate land value
            land_value = kaufvertrag_data.purchase_price - building_value

            # Parse address components
            street = kaufvertrag_data.street or kaufvertrag_data.property_address
            city = kaufvertrag_data.city or "Unknown"
            postal_code = kaufvertrag_data.postal_code or "0000"

            # Determine depreciation rate based on construction year
            depreciation_rate = self._calculate_depreciation_rate(
                kaufvertrag_data.construction_year, kaufvertrag_data.purchase_date
            )

            property_obj = Property(
                user_id=user_id,
                property_type=PropertyType.RENTAL,
                rental_percentage=Decimal("100.00"),
                address=kaufvertrag_data.property_address,
                street=street,
                city=city,
                postal_code=postal_code,
                purchase_date=kaufvertrag_data.purchase_date,
                purchase_price=kaufvertrag_data.purchase_price,
                building_value=building_value,
                land_value=land_value,
                grunderwerbsteuer=kaufvertrag_data.grunderwerbsteuer,
                notary_fees=kaufvertrag_data.notary_fees,
                registry_fees=kaufvertrag_data.registry_fees,
                construction_year=kaufvertrag_data.construction_year,
                depreciation_rate=depreciation_rate,
                status=PropertyStatus.ACTIVE,
                kaufvertrag_document_id=document_id,
            )

            self.db.add(property_obj)
            self.db.flush()  # Get property ID

            logger.info(
                "Created new property from Kaufvertrag",
                extra={
                    "property_id": str(property_obj.id),
                    "address": kaufvertrag_data.property_address,
                },
            )

        return property_obj, property_created

    def create_purchase_cost_transactions(
        self, kaufvertrag_data: KaufvertragData, user_id: int, property_id: UUID
    ) -> List[Transaction]:
        """
        Create expense transactions for purchase costs.

        Creates transactions for:
        - Grunderwerbsteuer (property transfer tax)
        - Eintragungsgebühr (registry fees)
        - Notarkosten (notary fees)

        Args:
            kaufvertrag_data: Extracted Kaufvertrag data
            user_id: ID of the user
            property_id: UUID of the property

        Returns:
            List of created Transaction objects
        """
        transactions = []
        purchase_date = kaufvertrag_data.purchase_date

        # Grunderwerbsteuer (property transfer tax)
        if kaufvertrag_data.grunderwerbsteuer and kaufvertrag_data.grunderwerbsteuer > 0:
            transaction = Transaction(
                user_id=user_id,
                property_id=property_id,
                type=TransactionType.EXPENSE,
                amount=kaufvertrag_data.grunderwerbsteuer,
                transaction_date=purchase_date,
                description=f"Grunderwerbsteuer - {kaufvertrag_data.property_address}",
                expense_category=ExpenseCategory.PROPERTY_TAX,
                is_deductible=False,  # Not deductible, part of acquisition cost
                is_system_generated=True,
                import_source="kaufvertrag_import",
                classification_confidence=Decimal("0.95"),
            )
            self.db.add(transaction)
            transactions.append(transaction)

        # Eintragungsgebühr (registry fees)
        if kaufvertrag_data.registry_fees and kaufvertrag_data.registry_fees > 0:
            transaction = Transaction(
                user_id=user_id,
                property_id=property_id,
                type=TransactionType.EXPENSE,
                amount=kaufvertrag_data.registry_fees,
                transaction_date=purchase_date,
                description=f"Eintragungsgebühr - {kaufvertrag_data.property_address}",
                expense_category=ExpenseCategory.PROFESSIONAL_SERVICES,
                is_deductible=False,  # Not deductible, part of acquisition cost
                is_system_generated=True,
                import_source="kaufvertrag_import",
                classification_confidence=Decimal("0.95"),
            )
            self.db.add(transaction)
            transactions.append(transaction)

        # Notarkosten (notary fees)
        if kaufvertrag_data.notary_fees and kaufvertrag_data.notary_fees > 0:
            transaction = Transaction(
                user_id=user_id,
                property_id=property_id,
                type=TransactionType.EXPENSE,
                amount=kaufvertrag_data.notary_fees,
                transaction_date=purchase_date,
                description=f"Notarkosten - {kaufvertrag_data.property_address}",
                expense_category=ExpenseCategory.PROFESSIONAL_SERVICES,
                is_deductible=False,  # Not deductible, part of acquisition cost
                is_system_generated=True,
                import_source="kaufvertrag_import",
                classification_confidence=Decimal("0.95"),
            )
            self.db.add(transaction)
            transactions.append(transaction)

        self.db.flush()  # Get transaction IDs

        logger.info(
            "Created purchase cost transactions",
            extra={
                "property_id": str(property_id),
                "transaction_count": len(transactions),
                "total_amount": float(sum(t.amount for t in transactions)),
            },
        )

        return transactions

    def initialize_depreciation_schedule(
        self, property_id: UUID, building_value: Decimal, purchase_date: date
    ) -> Dict[str, Any]:
        """
        Initialize historical depreciation schedule.

        Uses HistoricalDepreciationService to backfill depreciation
        transactions from purchase date to current year.

        Args:
            property_id: UUID of the property
            building_value: Building value for depreciation calculation
            purchase_date: Date of property purchase

        Returns:
            Dictionary with backfill results:
            {
                "years_backfilled": int,
                "total_amount": Decimal,
                "transaction_ids": List[int]
            }
        """
        # Get user_id from property
        property_obj = self.db.query(Property).filter(Property.id == property_id).first()
        if not property_obj:
            raise ValueError(f"Property not found: {property_id}")

        # Backfill depreciation using HistoricalDepreciationService
        result = self.depreciation_service.backfill_depreciation(
            property_id=property_id, user_id=property_obj.user_id, confirm=True
        )

        logger.info(
            "Initialized depreciation schedule",
            extra={
                "property_id": str(property_id),
                "years_backfilled": result.years_backfilled,
                "total_amount": float(result.total_amount),
            },
        )

        return {
            "years_backfilled": result.years_backfilled,
            "total_amount": result.total_amount,
            "transaction_ids": [t.id for t in result.transactions],
        }

    def _calculate_depreciation_rate(
        self, construction_year: Optional[int], purchase_date: date
    ) -> Decimal:
        """
        Calculate depreciation rate based on building age.

        Austrian tax law:
        - Buildings constructed before 1915: 2.5% AfA (40 years)
        - Buildings constructed 1915 or later: 2.0% AfA (50 years)

        Args:
            construction_year: Year the building was constructed
            purchase_date: Date of property purchase

        Returns:
            Depreciation rate as Decimal (e.g., 0.02 for 2%)
        """
        if construction_year and construction_year < 1915:
            return Decimal("0.025")  # 2.5% for old buildings
        else:
            return Decimal("0.02")  # 2.0% for newer buildings
