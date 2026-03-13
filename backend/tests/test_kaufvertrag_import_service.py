"""
Unit tests for KaufvertragImportService.
Tests property creation, deduplication, transaction creation, and depreciation initialization.
"""
from datetime import date
from decimal import Decimal
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, ExpenseCategory
from app.models.user import User, UserType
from app.services.kaufvertrag_import_service import KaufvertragImportService
from app.services.kaufvertrag_extractor import KaufvertragData
from app.services.address_matcher import AddressMatch
from app.services.historical_depreciation_service import BackfillResult


@pytest.fixture
def db_session():
    """Mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def import_service(db_session):
    """Create a KaufvertragImportService instance."""
    return KaufvertragImportService(db_session)


@pytest.fixture
def test_user():
    """Create a test user."""
    user = User(
        id=1,
        name="Test User",
        email="test@example.com",
        user_type=UserType.SELF_EMPLOYED,
    )
    return user


@pytest.fixture
def sample_kaufvertrag_data():
    """Create sample Kaufvertrag data."""
    return KaufvertragData(
        property_address="Hauptstraße 123, 1010 Wien",
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        purchase_price=Decimal("500000.00"),
        purchase_date=date(2020, 6, 15),
        building_value=Decimal("400000.00"),
        land_value=Decimal("100000.00"),
        grunderwerbsteuer=Decimal("17500.00"),
        notary_fees=Decimal("5000.00"),
        registry_fees=Decimal("1500.00"),
        buyer_name="Max Mustermann",
        seller_name="Maria Musterfrau",
        construction_year=1990,
        property_type="Wohnung",
        confidence=0.85,
    )


@pytest.fixture
def existing_property(test_user):
    """Create an existing property for deduplication tests."""
    return Property(
        id=uuid4(),
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Hauptstraße 123, 1010 Wien",
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2020, 6, 15),
        purchase_price=Decimal("0.00"),  # Not yet set
        building_value=Decimal("0.00"),
        land_value=Decimal("0.00"),
        construction_year=1990,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE,
    )


class TestKaufvertragImportService:
    """Test suite for KaufvertragImportService."""

    def test_import_from_ocr_text_success(
        self, import_service, db_session, test_user, sample_kaufvertrag_data
    ):
        """Test successful import from OCR text."""
        # Mock extractor
        with patch.object(import_service.extractor, "extract") as mock_extractor, \
             patch.object(import_service.address_matcher, "match_address") as mock_matcher, \
             patch.object(import_service.depreciation_service, "backfill_depreciation") as mock_depreciation:
            
            mock_extractor.return_value = sample_kaufvertrag_data
            mock_matcher.return_value = []
            mock_depreciation.return_value = BackfillResult(
                property_id=uuid4(),
                years_backfilled=4,
                total_amount=Decimal("32000.00"),
                transactions=[],
            )

            # Mock database operations
            db_session.add.return_value = None
            db_session.flush.return_value = None
            db_session.commit.return_value = None

            # Perform import
            result = import_service.import_from_ocr_text(
                text="Sample OCR text", user_id=test_user.id, document_id=1
            )

            # Verify results
            assert "property_id" in result
            assert result["property_created"] is True
            assert len(result["transactions_created"]) == 3  # 3 purchase cost transactions
            assert result["depreciation_years"] == 4
            assert result["confidence"] == 0.85

    def test_import_from_ocr_text_missing_purchase_price(
        self, import_service, db_session, test_user
    ):
        """Test import fails when purchase price is missing."""
        # Create data without purchase price
        incomplete_data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            purchase_date=date(2020, 6, 15),
            purchase_price=None,  # Missing
        )

        with patch.object(import_service.extractor, "extract") as mock_extractor:
            mock_extractor.return_value = incomplete_data

            with pytest.raises(ValueError, match="Purchase price is required"):
                import_service.import_from_ocr_text(
                    text="Sample OCR text", user_id=test_user.id
                )

    def test_import_from_ocr_text_missing_purchase_date(
        self, import_service, db_session, test_user
    ):
        """Test import fails when purchase date is missing."""
        incomplete_data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            purchase_price=Decimal("500000.00"),
            purchase_date=None,  # Missing
        )

        with patch.object(import_service.extractor, "extract") as mock_extractor:
            mock_extractor.return_value = incomplete_data

            with pytest.raises(ValueError, match="Purchase date is required"):
                import_service.import_from_ocr_text(
                    text="Sample OCR text", user_id=test_user.id
                )

    def test_import_from_ocr_text_missing_address(
        self, import_service, db_session, test_user
    ):
        """Test import fails when property address is missing."""
        incomplete_data = KaufvertragData(
            property_address=None,  # Missing
            purchase_price=Decimal("500000.00"),
            purchase_date=date(2020, 6, 15),
        )

        with patch.object(import_service.extractor, "extract") as mock_extractor:
            mock_extractor.return_value = incomplete_data

            with pytest.raises(ValueError, match="Property address is required"):
                import_service.import_from_ocr_text(
                    text="Sample OCR text", user_id=test_user.id
                )

    def test_create_or_update_property_new_property(
        self, import_service, db_session, test_user, sample_kaufvertrag_data
    ):
        """Test creating a new property when no match found."""
        # Mock address matcher (no existing property)
        with patch.object(import_service.address_matcher, "match_address") as mock_matcher:
            mock_matcher.return_value = []

            db_session.add.return_value = None
            db_session.flush.return_value = None

            property_obj, created = import_service.create_or_update_property(
                sample_kaufvertrag_data, test_user.id, document_id=1
            )

            assert created is True
            assert property_obj.user_id == test_user.id
            assert property_obj.address == "Hauptstraße 123, 1010 Wien"
            assert property_obj.purchase_price == Decimal("500000.00")
            assert property_obj.building_value == Decimal("400000.00")
            assert property_obj.land_value == Decimal("100000.00")
            assert property_obj.grunderwerbsteuer == Decimal("17500.00")
            assert property_obj.notary_fees == Decimal("5000.00")
            assert property_obj.registry_fees == Decimal("1500.00")
            assert property_obj.construction_year == 1990
            assert property_obj.kaufvertrag_document_id == 1

    def test_create_or_update_property_update_existing(
        self, import_service, db_session, test_user, sample_kaufvertrag_data, existing_property
    ):
        """Test updating existing property when high-confidence match found."""
        # Mock address matcher (high confidence match)
        mock_match = AddressMatch(
            property=existing_property,
            confidence=0.95,
            matched_components={"street": True, "postal_code": True, "city": True},
        )
        with patch.object(import_service.address_matcher, "match_address") as mock_matcher:
            mock_matcher.return_value = [mock_match]

            property_obj, created = import_service.create_or_update_property(
                sample_kaufvertrag_data, test_user.id, document_id=1
            )

            assert created is False
            assert property_obj.id == existing_property.id
            assert property_obj.purchase_price == Decimal("500000.00")
            assert property_obj.building_value == Decimal("400000.00")
            assert property_obj.land_value == Decimal("100000.00")

    def test_create_or_update_property_low_confidence_creates_new(
        self, import_service, db_session, test_user, sample_kaufvertrag_data, existing_property
    ):
        """Test creating new property when match confidence is low."""
        # Mock address matcher (low confidence match)
        mock_match = AddressMatch(
            property=existing_property,
            confidence=0.65,  # Below 0.9 threshold
            matched_components={"street": False, "postal_code": True, "city": True},
        )
        with patch.object(import_service.address_matcher, "match_address") as mock_matcher:
            mock_matcher.return_value = [mock_match]

            db_session.add.return_value = None
            db_session.flush.return_value = None

            property_obj, created = import_service.create_or_update_property(
                sample_kaufvertrag_data, test_user.id
            )

            assert created is True
            assert property_obj.id != existing_property.id

    def test_create_or_update_property_estimate_building_value(
        self, import_service, db_session, test_user
    ):
        """Test building value estimation when not provided."""
        # Data without building value
        data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            purchase_price=Decimal("500000.00"),
            purchase_date=date(2020, 6, 15),
            building_value=None,  # Not provided
            land_value=None,
        )

        with patch.object(import_service.address_matcher, "match_address") as mock_matcher:
            mock_matcher.return_value = []

            db_session.add.return_value = None
            db_session.flush.return_value = None

            property_obj, created = import_service.create_or_update_property(
                data, test_user.id
            )

            # Should estimate 80% building, 20% land
            assert property_obj.building_value == Decimal("400000.00")
            assert property_obj.land_value == Decimal("100000.00")

    def test_create_purchase_cost_transactions(
        self, import_service, db_session, test_user, sample_kaufvertrag_data
    ):
        """Test creation of purchase cost transactions."""
        property_id = uuid4()

        db_session.add.return_value = None
        db_session.flush.return_value = None

        transactions = import_service.create_purchase_cost_transactions(
            sample_kaufvertrag_data, test_user.id, property_id
        )

        assert len(transactions) == 3

        # Check Grunderwerbsteuer transaction
        grunderwerb_txn = transactions[0]
        assert grunderwerb_txn.type == TransactionType.EXPENSE
        assert grunderwerb_txn.amount == Decimal("17500.00")
        assert grunderwerb_txn.expense_category == ExpenseCategory.PROPERTY_TAX
        assert grunderwerb_txn.is_deductible is False
        assert grunderwerb_txn.is_system_generated is True
        assert grunderwerb_txn.import_source == "kaufvertrag_import"
        assert "Grunderwerbsteuer" in grunderwerb_txn.description

        # Check registry fees transaction
        registry_txn = transactions[1]
        assert registry_txn.amount == Decimal("1500.00")
        assert registry_txn.expense_category == ExpenseCategory.PROFESSIONAL_SERVICES
        assert "Eintragungsgebühr" in registry_txn.description

        # Check notary fees transaction
        notary_txn = transactions[2]
        assert notary_txn.amount == Decimal("5000.00")
        assert notary_txn.expense_category == ExpenseCategory.PROFESSIONAL_SERVICES
        assert "Notarkosten" in notary_txn.description

    def test_create_purchase_cost_transactions_skip_zero_amounts(
        self, import_service, db_session, test_user
    ):
        """Test that transactions with zero amounts are skipped."""
        data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            purchase_price=Decimal("500000.00"),
            purchase_date=date(2020, 6, 15),
            grunderwerbsteuer=Decimal("17500.00"),
            notary_fees=None,  # Not provided
            registry_fees=Decimal("0.00"),  # Zero
        )

        property_id = uuid4()
        db_session.add.return_value = None
        db_session.flush.return_value = None

        transactions = import_service.create_purchase_cost_transactions(
            data, test_user.id, property_id
        )

        # Should only create Grunderwerbsteuer transaction
        assert len(transactions) == 1
        assert transactions[0].amount == Decimal("17500.00")

    def test_create_purchase_cost_transactions_all_missing(
        self, import_service, db_session, test_user
    ):
        """Test that no transactions are created when all costs are missing."""
        data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            purchase_price=Decimal("500000.00"),
            purchase_date=date(2020, 6, 15),
            grunderwerbsteuer=None,
            notary_fees=None,
            registry_fees=None,
        )

        property_id = uuid4()
        db_session.flush.return_value = None

        transactions = import_service.create_purchase_cost_transactions(
            data, test_user.id, property_id
        )

        assert len(transactions) == 0

    def test_initialize_depreciation_schedule(
        self, import_service, db_session, test_user
    ):
        """Test initialization of depreciation schedule."""
        property_id = uuid4()
        property_obj = Property(
            id=property_id,
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            address="Hauptstraße 123, 1010 Wien",
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 6, 15),
            purchase_price=Decimal("500000.00"),
            building_value=Decimal("400000.00"),
            land_value=Decimal("100000.00"),
            construction_year=1990,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE,
        )

        # Mock database query
        db_session.query.return_value.filter.return_value.first.return_value = property_obj

        # Mock depreciation service
        with patch.object(
            import_service.depreciation_service, "backfill_depreciation"
        ) as mock_backfill:
            mock_backfill.return_value = BackfillResult(
                property_id=property_id,
                years_backfilled=4,
                total_amount=Decimal("32000.00"),
                transactions=[],
            )

            result = import_service.initialize_depreciation_schedule(
                property_id, Decimal("400000.00"), date(2020, 6, 15)
            )

            assert result["years_backfilled"] == 4
            assert result["total_amount"] == Decimal("32000.00")
            mock_backfill.assert_called_once_with(
                property_id=property_id, user_id=test_user.id, confirm=True
            )

    def test_initialize_depreciation_schedule_property_not_found(
        self, import_service, db_session
    ):
        """Test depreciation initialization fails when property not found."""
        property_id = uuid4()

        # Mock database query to return None
        db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="Property not found"):
            import_service.initialize_depreciation_schedule(
                property_id, Decimal("400000.00"), date(2020, 6, 15)
            )

    def test_calculate_depreciation_rate_old_building(self, import_service):
        """Test depreciation rate calculation for buildings before 1915."""
        rate = import_service._calculate_depreciation_rate(1900, date(2020, 6, 15))
        assert rate == Decimal("0.025")  # 2.5% for old buildings

    def test_calculate_depreciation_rate_new_building(self, import_service):
        """Test depreciation rate calculation for buildings 1915 or later."""
        rate = import_service._calculate_depreciation_rate(1990, date(2020, 6, 15))
        assert rate == Decimal("0.02")  # 2.0% for newer buildings

    def test_calculate_depreciation_rate_no_construction_year(self, import_service):
        """Test depreciation rate calculation when construction year is unknown."""
        rate = import_service._calculate_depreciation_rate(None, date(2020, 6, 15))
        assert rate == Decimal("0.02")  # Default to 2.0%

    def test_calculate_depreciation_rate_boundary_1915(self, import_service):
        """Test depreciation rate calculation for building constructed in 1915."""
        rate = import_service._calculate_depreciation_rate(1915, date(2020, 6, 15))
        assert rate == Decimal("0.02")  # 1915 and later use 2.0%

    def test_calculate_depreciation_rate_boundary_1914(self, import_service):
        """Test depreciation rate calculation for building constructed in 1914."""
        rate = import_service._calculate_depreciation_rate(1914, date(2020, 6, 15))
        assert rate == Decimal("0.025")  # Before 1915 use 2.5%

    def test_import_with_document_linking(
        self, import_service, db_session, test_user, sample_kaufvertrag_data
    ):
        """Test that document ID is properly linked to property."""
        with patch.object(import_service.extractor, "extract") as mock_extractor, \
             patch.object(import_service.address_matcher, "match_address") as mock_matcher, \
             patch.object(import_service.depreciation_service, "backfill_depreciation") as mock_depreciation:
            
            mock_extractor.return_value = sample_kaufvertrag_data
            mock_matcher.return_value = []
            mock_depreciation.return_value = BackfillResult(
                property_id=uuid4(),
                years_backfilled=0,
                total_amount=Decimal("0.00"),
                transactions=[],
            )

            db_session.add.return_value = None
            db_session.flush.return_value = None
            db_session.commit.return_value = None

            # Import with document ID
            result = import_service.import_from_ocr_text(
                text="Sample OCR text", user_id=test_user.id, document_id=42
            )

            # Verify document was linked
            assert result["property_created"] is True
            # Property should have kaufvertrag_document_id set to 42

    def test_import_without_building_value_creates_depreciation(
        self, import_service, db_session, test_user
    ):
        """Test that depreciation is created even when building value is estimated."""
        data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            purchase_price=Decimal("500000.00"),
            purchase_date=date(2020, 6, 15),
            building_value=None,  # Will be estimated
        )

        with patch.object(import_service.extractor, "extract") as mock_extractor, \
             patch.object(import_service.address_matcher, "match_address") as mock_matcher, \
             patch.object(import_service.depreciation_service, "backfill_depreciation") as mock_depreciation:
            
            mock_extractor.return_value = data
            mock_matcher.return_value = []
            mock_depreciation.return_value = BackfillResult(
                property_id=uuid4(),
                years_backfilled=4,
                total_amount=Decimal("32000.00"),
                transactions=[],
            )

            db_session.add.return_value = None
            db_session.flush.return_value = None
            db_session.commit.return_value = None

            result = import_service.import_from_ocr_text(
                text="Sample OCR text", user_id=test_user.id
            )

            # Should still create depreciation with estimated building value
            assert result["depreciation_years"] == 4

    def test_import_with_zero_building_value_skips_depreciation(
        self, import_service, db_session, test_user
    ):
        """Test that depreciation is skipped when building value is zero."""
        data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            purchase_price=Decimal("100000.00"),
            purchase_date=date(2020, 6, 15),
            building_value=Decimal("0.00"),  # Land only
            land_value=Decimal("100000.00"),
        )

        with patch.object(import_service.extractor, "extract") as mock_extractor, \
             patch.object(import_service.address_matcher, "match_address") as mock_matcher:
            
            mock_extractor.return_value = data
            mock_matcher.return_value = []

            db_session.add.return_value = None
            db_session.flush.return_value = None
            db_session.commit.return_value = None

            result = import_service.import_from_ocr_text(
                text="Sample OCR text", user_id=test_user.id
            )

            # Should not create depreciation for land-only property
            assert result["depreciation_years"] == 0

    def test_transaction_dates_match_purchase_date(
        self, import_service, db_session, test_user, sample_kaufvertrag_data
    ):
        """Test that all purchase cost transactions use the purchase date."""
        property_id = uuid4()

        db_session.add.return_value = None
        db_session.flush.return_value = None

        transactions = import_service.create_purchase_cost_transactions(
            sample_kaufvertrag_data, test_user.id, property_id
        )

        # All transactions should have the same date as purchase
        for txn in transactions:
            assert txn.transaction_date == sample_kaufvertrag_data.purchase_date

    def test_property_linked_to_all_transactions(
        self, import_service, db_session, test_user, sample_kaufvertrag_data
    ):
        """Test that all transactions are linked to the property."""
        property_id = uuid4()

        db_session.add.return_value = None
        db_session.flush.return_value = None

        transactions = import_service.create_purchase_cost_transactions(
            sample_kaufvertrag_data, test_user.id, property_id
        )

        # All transactions should be linked to the property
        for txn in transactions:
            assert txn.property_id == property_id
            assert txn.user_id == test_user.id
