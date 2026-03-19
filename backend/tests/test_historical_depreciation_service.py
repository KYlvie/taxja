"""
Unit tests for Historical Depreciation Service
"""

import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4

from app.services.historical_depreciation_service import (
    HistoricalDepreciationService,
    HistoricalDepreciationYear,
    BackfillResult
)
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, ExpenseCategory
from app.models.user import User
from app.models.chat_message import ChatMessage  # noqa: F401 - needed for User relationship
from app.models.document import Document  # noqa: F401 - needed for Property relationship


@pytest.fixture
def user(db):
    """Create test user"""
    user = User(
        email="test@example.com",
        name="Test User",
        password_hash="hashed",
        user_type="self_employed"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def property_2020(db, user):
    """Create property purchased in 2020"""
    property = Property(
        user_id=user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Hauptstraße 123, 1010 Wien",
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2020, 6, 15),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        land_value=Decimal("70000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property


@pytest.fixture
def property_current_year(db, user):
    """Create property purchased in current year"""
    current_year = date.today().year
    property = Property(
        user_id=user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Neubaugasse 45, 1070 Wien",
        street="Neubaugasse 45",
        city="Wien",
        postal_code="1070",
        purchase_date=date(current_year, 3, 1),
        purchase_price=Decimal("400000.00"),
        building_value=Decimal("320000.00"),
        land_value=Decimal("80000.00"),
        construction_year=2000,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property


@pytest.fixture
def service(db):
    """Create historical depreciation service"""
    return HistoricalDepreciationService(db)


class TestHistoricalDepreciationYear:
    """Test HistoricalDepreciationYear data class"""
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        year_data = HistoricalDepreciationYear(
            year=2020,
            amount=Decimal("5600.00"),
            transaction_date=date(2020, 12, 31)
        )
        
        result = year_data.to_dict()
        
        assert result["year"] == 2020
        assert result["amount"] == 5600.00
        assert result["transaction_date"] == "2020-12-31"


class TestBackfillResult:
    """Test BackfillResult data class"""
    
    def test_to_dict(self, db, user, property_2020):
        """Test conversion to dictionary"""
        transactions = [
            Transaction(
                id=1,
                user_id=user.id,
                property_id=property_2020.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("5600.00"),
                transaction_date=date(2020, 12, 31),
                expense_category=ExpenseCategory.DEPRECIATION_AFA
            )
        ]
        
        result = BackfillResult(
            property_id=property_2020.id,
            years_backfilled=1,
            total_amount=Decimal("5600.00"),
            transactions=transactions
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["property_id"] == str(property_2020.id)
        assert result_dict["years_backfilled"] == 1
        assert result_dict["total_amount"] == 5600.00
        assert result_dict["transaction_ids"] == [1]


class TestCalculateHistoricalDepreciation:
    """Test calculate_historical_depreciation method"""
    
    def test_property_purchased_in_2020(self, service, property_2020):
        """Test calculation for property purchased in 2020"""
        current_year = date.today().year
        
        results = service.calculate_historical_depreciation(property_2020.id)
        
        # Should have depreciation for 2020 through current year
        expected_years = current_year - 2020 + 1
        assert len(results) == expected_years
        
        # Check first year (2020) - pro-rated for 7 months (June-December)
        first_year = results[0]
        assert first_year.year == 2020
        assert first_year.transaction_date == date(2020, 12, 31)
        # Residential buildings now use 1.5% AfA.
        # 280000 * 0.015 * 7/12 = 2450.00
        assert abs(first_year.amount - Decimal("2450.00")) < Decimal("0.01")
        
        # Check second year (2021) - full year
        if len(results) > 1:
            second_year = results[1]
            assert second_year.year == 2021
            assert second_year.transaction_date == date(2021, 12, 31)
            # 280000 * 0.015 = 4200.00
            assert second_year.amount == Decimal("4200.00")
    
    def test_property_purchased_current_year(self, service, property_current_year):
        """Test calculation for property purchased in current year"""
        current_year = date.today().year
        
        results = service.calculate_historical_depreciation(property_current_year.id)
        
        # Should have only current year
        assert len(results) == 1
        assert results[0].year == current_year
        
        # Pro-rated for months owned (March-December = 10 months)
        # 320000 * 0.015 * 10/12 = 4000.00
        expected = Decimal("320000") * Decimal("0.015") * 10 / 12
        assert abs(results[0].amount - expected.quantize(Decimal("0.01"))) < Decimal("0.01")
    
    def test_skip_existing_depreciation(self, service, db, property_2020, user):
        """Test that existing depreciation years are skipped"""
        # Create depreciation for 2020
        existing_transaction = Transaction(
            user_id=user.id,
            property_id=property_2020.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("3266.67"),
            transaction_date=date(2020, 12, 31),
            expense_category=ExpenseCategory.DEPRECIATION_AFA,
            is_system_generated=True
        )
        db.add(existing_transaction)
        db.commit()
        
        results = service.calculate_historical_depreciation(property_2020.id)
        
        # Should not include 2020
        years = [r.year for r in results]
        assert 2020 not in years
        assert 2021 in years  # Should have 2021 and later
    
    def test_property_not_found(self, service):
        """Test error when property not found"""
        fake_id = uuid4()
        
        with pytest.raises(ValueError, match="Property not found"):
            service.calculate_historical_depreciation(fake_id)
    
    def test_owner_occupied_property(self, service, db, user):
        """Test that owner-occupied properties have no depreciation"""
        property = Property(
            user_id=user.id,
            property_type=PropertyType.OWNER_OCCUPIED,
            rental_percentage=Decimal("0.00"),
            address="Wohnung 1, 1010 Wien",
            street="Wohnung 1",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            land_value=Decimal("60000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        
        results = service.calculate_historical_depreciation(property.id)
        
        # Owner-occupied properties are not depreciable
        assert len(results) == 0


class TestBackfillDepreciation:
    """Test backfill_depreciation method"""
    
    def test_preview_mode(self, service, property_2020, user):
        """Test preview mode (confirm=False)"""
        result = service.backfill_depreciation(
            property_2020.id,
            user.id,
            confirm=False
        )
        
        assert result.property_id == property_2020.id
        assert result.years_backfilled > 0
        assert result.total_amount > 0
        assert len(result.transactions) == 0  # No transactions created
    
    def test_create_transactions(self, service, db, property_2020, user):
        """Test creating historical depreciation transactions"""
        result = service.backfill_depreciation(
            property_2020.id,
            user.id,
            confirm=True
        )
        
        current_year = date.today().year
        expected_years = current_year - 2020 + 1
        
        assert result.property_id == property_2020.id
        assert result.years_backfilled == expected_years
        assert len(result.transactions) == expected_years
        
        # Verify transactions in database
        transactions = db.query(Transaction).filter(
            Transaction.property_id == property_2020.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        ).all()
        
        assert len(transactions) == expected_years
        
        # Check first transaction (2020)
        first_tx = next(t for t in transactions if t.transaction_date.year == 2020)
        assert first_tx.type == TransactionType.EXPENSE
        assert first_tx.is_system_generated is True
        assert first_tx.is_deductible is True
        assert first_tx.import_source == "historical_backfill"
        assert first_tx.classification_confidence == Decimal("1.0")
        assert "AfA" in first_tx.description
        assert "2020" in first_tx.description
        assert first_tx.transaction_date == date(2020, 12, 31)
    
    def test_ownership_validation(self, service, property_2020, db):
        """Test that ownership is validated"""
        # Create different user
        other_user = User(
            email="other@example.com",
            name="Other User",
            password_hash="hashed",
            user_type="employee"
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)
        
        with pytest.raises(ValueError, match="Property with id .* not found"):
            service.backfill_depreciation(
                property_2020.id,
                other_user.id,
                confirm=True
            )
    
    def test_prevent_duplicates(self, service, db, property_2020, user):
        """Test that duplicate transactions are prevented"""
        # First backfill
        result1 = service.backfill_depreciation(
            property_2020.id,
            user.id,
            confirm=True
        )
        
        # Second backfill should create no new transactions
        result2 = service.backfill_depreciation(
            property_2020.id,
            user.id,
            confirm=True
        )
        
        assert result2.years_backfilled == 0
        assert result2.total_amount == 0
        assert len(result2.transactions) == 0
    
    def test_rollback_on_error(self, service, db, property_2020, user, monkeypatch):
        """Test that transactions are rolled back on error"""
        # Mock db.commit to raise an error
        original_commit = db.commit
        
        def mock_commit():
            raise RuntimeError("Database error")
        
        monkeypatch.setattr(db, "commit", mock_commit)
        
        with pytest.raises(RuntimeError, match="Failed to backfill depreciation"):
            service.backfill_depreciation(
                property_2020.id,
                user.id,
                confirm=True
            )
        
        # Restore original commit
        monkeypatch.setattr(db, "commit", original_commit)
        
        # Verify no transactions were created
        transactions = db.query(Transaction).filter(
            Transaction.property_id == property_2020.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        ).all()
        
        assert len(transactions) == 0
    
    def test_respects_building_value_limit(self, service, db, user):
        """Test that depreciation stops when building value is reached"""
        # Create property with small building value that will be fully depreciated quickly
        property = Property(
            user_id=user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            address="Small Property, 1010 Wien",
            street="Small Property",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2000, 1, 1),  # 25+ years ago
            purchase_price=Decimal("100000.00"),
            building_value=Decimal("80000.00"),
            land_value=Decimal("20000.00"),
            construction_year=1985,
            depreciation_rate=Decimal("0.02"),  # 2% = 1600/year, fully depreciated in 50 years
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        
        result = service.backfill_depreciation(
            property.id,
            user.id,
            confirm=True
        )
        
        # Calculate total depreciation
        total_depreciation = sum(t.amount for t in result.transactions)
        
        # Should not exceed building value
        assert total_depreciation <= property.building_value
        
        # Residential buildings now use 1.5% AfA:
        # - Years owned: 2000 to current year
        # - Expected depreciation: 80000 * 0.015 * years_owned
        # - Should be close to this amount
        current_year = date.today().year
        years_owned = current_year - 2000 + 1
        expected_depreciation = property.building_value * Decimal("0.015") * years_owned
        
        # Allow for rounding differences
        assert abs(total_depreciation - expected_depreciation) < Decimal("100.00")


class TestMixedUseProperty:
    """Test historical depreciation for mixed-use properties"""
    
    def test_mixed_use_50_percent(self, service, db, user):
        """Test mixed-use property with 50% rental"""
        property = Property(
            user_id=user.id,
            property_type=PropertyType.MIXED_USE,
            rental_percentage=Decimal("50.00"),
            address="Mixed Use, 1010 Wien",
            street="Mixed Use",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2023, 1, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
            land_value=Decimal("80000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        
        results = service.calculate_historical_depreciation(property.id)
        
        # Should have depreciation for 2023 and current year
        assert len(results) >= 1
        
        # Check 2023 depreciation (full year)
        year_2023 = next((r for r in results if r.year == 2023), None)
        assert year_2023 is not None
        
        # 320000 * 0.50 * 0.015 = 2400.00
        expected = Decimal("320000") * Decimal("0.50") * Decimal("0.015")
        assert year_2023.amount == expected.quantize(Decimal("0.01"))
