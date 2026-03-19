"""Tests for AddressMatcher service"""
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.property import Property, PropertyStatus, PropertyType
from app.models.user import User
from app.services.address_matcher import AddressMatcher, AddressMatch


@pytest.fixture
def db_session(db: Session):
    """Reuse the shared isolated SQLite test session."""
    yield db


@pytest.fixture
def test_user(db_session: Session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        name="Test User",
        user_type="landlord",
        language="de"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_properties(db_session: Session, test_user: User):
    """Create test properties with various addresses"""
    properties = [
        Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            address="Hauptstraße 123, 1010 Wien",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("350000.00"),
            building_value=Decimal("280000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        ),
        Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            street="Mariahilfer Straße 45",
            city="Wien",
            postal_code="1060",
            address="Mariahilfer Straße 45, 1060 Wien",
            purchase_date=date(2019, 6, 15),
            purchase_price=Decimal("420000.00"),
            building_value=Decimal("336000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        ),
        Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            street="Linzer Gasse 78",
            city="Salzburg",
            postal_code="5020",
            address="Linzer Gasse 78, 5020 Salzburg",
            purchase_date=date(2021, 3, 10),
            purchase_price=Decimal("280000.00"),
            building_value=Decimal("224000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        ),
        Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            street="Ringstraße 12",
            city="Wien",
            postal_code="1010",
            address="Ringstraße 12, 1010 Wien",
            purchase_date=date(2018, 9, 1),
            purchase_price=Decimal("500000.00"),
            building_value=Decimal("400000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.SOLD,
            sale_date=date(2023, 12, 31)
        ),
    ]
    
    for prop in properties:
        db_session.add(prop)
    
    db_session.commit()
    
    for prop in properties:
        db_session.refresh(prop)
    
    return properties


class TestAddressMatcher:
    """Test suite for AddressMatcher"""
    
    def test_exact_match(self, db_session: Session, test_user: User, test_properties: list):
        """Test exact address match returns high confidence"""
        matcher = AddressMatcher(db_session)
        
        # Exact match with first property
        matches = matcher.match_address("Hauptstraße 123, 1010 Wien", test_user.id)
        
        assert len(matches) > 0
        assert matches[0].property.street == "Hauptstraße 123"
        assert matches[0].confidence > 0.9
        assert matches[0].matched_components["street"] is True
        assert matches[0].matched_components["postal_code"] is True
    
    def test_normalized_match(self, db_session: Session, test_user: User, test_properties: list):
        """Test that address normalization works (Str. vs Straße)"""
        matcher = AddressMatcher(db_session)
        
        # Use "Str." abbreviation instead of "Straße"
        matches = matcher.match_address("Hauptstr. 123, 1010 Wien", test_user.id)
        
        assert len(matches) > 0
        # Should still match the Hauptstraße property
        hauptstrasse_match = next((m for m in matches if "Haupt" in m.property.street), None)
        assert hauptstrasse_match is not None
        assert hauptstrasse_match.confidence >= 0.7
    
    def test_partial_address_match(self, db_session: Session, test_user: User, test_properties: list):
        """Test matching with partial address (street only)"""
        matcher = AddressMatcher(db_session)
        
        matches = matcher.match_address("Mariahilfer Straße 45", test_user.id)
        
        assert len(matches) > 0
        mariahilfer_match = next((m for m in matches if "Mariahilfer" in m.property.street), None)
        assert mariahilfer_match is not None
        assert mariahilfer_match.confidence >= 0.7
    
    def test_postal_code_bonus(self, db_session: Session, test_user: User, test_properties: list):
        """Test that postal code match increases confidence"""
        matcher = AddressMatcher(db_session)
        
        # Match with postal code
        matches_with_postal = matcher.match_address("Hauptstraße 123, 1010", test_user.id)
        
        # Match without postal code
        matches_without_postal = matcher.match_address("Hauptstraße 123", test_user.id)
        
        # Find the Hauptstraße property in both results
        match_with = next((m for m in matches_with_postal if "Haupt" in m.property.street), None)
        match_without = next((m for m in matches_without_postal if "Haupt" in m.property.street), None)
        
        if match_with and match_without:
            # Confidence should be higher with postal code
            assert match_with.confidence >= match_without.confidence
            assert match_with.matched_components["postal_code"] is True
    
    def test_no_match_below_threshold(self, db_session: Session, test_user: User, test_properties: list):
        """Test that low confidence matches are filtered out"""
        matcher = AddressMatcher(db_session)
        
        # Completely different address
        matches = matcher.match_address("Nonexistent Street 999, 9999 Nowhere", test_user.id)
        
        # Should return empty list (all matches below 0.7 threshold)
        assert len(matches) == 0
    
    def test_multiple_matches_sorted(self, db_session: Session, test_user: User, test_properties: list):
        """Test that multiple matches are sorted by confidence"""
        matcher = AddressMatcher(db_session)
        
        # Search for "Wien" - should match multiple properties
        matches = matcher.match_address("Wien 1010", test_user.id)
        
        if len(matches) > 1:
            # Verify sorted by confidence descending
            for i in range(len(matches) - 1):
                assert matches[i].confidence >= matches[i + 1].confidence
    
    def test_only_active_properties(self, db_session: Session, test_user: User, test_properties: list):
        """Test that only active properties are matched (not sold/archived)"""
        matcher = AddressMatcher(db_session)
        
        # Try to match the sold property (Ringstraße)
        matches = matcher.match_address("Ringstraße 12, 1010 Wien", test_user.id)
        
        # Should not match the sold property
        ringstrasse_match = next((m for m in matches if "Ringstraße" in m.property.street), None)
        assert ringstrasse_match is None
    
    def test_user_isolation(self, db_session: Session, test_user: User, test_properties: list):
        """Test that matches are isolated to user's properties"""
        # Create another user
        other_user = User(
            email="other@example.com",
            password_hash="hashed_password",
            name="Other User",
            user_type="landlord",
            language="de"
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)
        
        matcher = AddressMatcher(db_session)
        
        # Search with other user's ID
        matches = matcher.match_address("Hauptstraße 123, 1010 Wien", other_user.id)
        
        # Should return no matches (properties belong to test_user)
        assert len(matches) == 0
    
    def test_empty_address_string(self, db_session: Session, test_user: User, test_properties: list):
        """Test handling of empty address string"""
        matcher = AddressMatcher(db_session)
        
        matches = matcher.match_address("", test_user.id)
        
        # Should return empty list
        assert len(matches) == 0
    
    def test_no_properties(self, db_session: Session, test_user: User):
        """Test behavior when user has no properties"""
        # Create a new user with no properties
        new_user = User(
            email="newuser@example.com",
            password_hash="hashed_password",
            name="New User",
            user_type="landlord",
            language="de"
        )
        db_session.add(new_user)
        db_session.commit()
        db_session.refresh(new_user)
        
        matcher = AddressMatcher(db_session)
        
        matches = matcher.match_address("Hauptstraße 123, 1010 Wien", new_user.id)
        
        # Should return empty list
        assert len(matches) == 0
    
    def test_address_normalization(self, db_session: Session, test_user: User):
        """Test address normalization function"""
        matcher = AddressMatcher(db_session)
        
        # Test various normalizations
        assert matcher._normalize_address("Hauptstraße 123") == "hauptstrasse 123"
        assert matcher._normalize_address("Haupt-Str. 123") == "haupt-strasse 123"
        assert matcher._normalize_address("  Extra   Spaces  ") == "extra spaces"
        assert matcher._normalize_address("Mariahilfer Straße") == "mariahilfer strasse"
    
    def test_confidence_levels(self, db_session: Session, test_user: User, test_properties: list):
        """Test that confidence levels are correctly categorized"""
        matcher = AddressMatcher(db_session)
        
        # High confidence match (exact)
        matches = matcher.match_address("Hauptstraße 123, 1010 Wien", test_user.id)
        high_confidence = [m for m in matches if m.confidence > 0.9]
        
        # Should have at least one high confidence match
        assert len(high_confidence) > 0
        
        # All returned matches should be >= 0.7 (threshold)
        for match in matches:
            assert match.confidence >= 0.7
    
    def test_matched_components(self, db_session: Session, test_user: User, test_properties: list):
        """Test that matched_components dictionary is populated correctly"""
        matcher = AddressMatcher(db_session)
        
        matches = matcher.match_address("Hauptstraße 123, 1010 Wien", test_user.id)
        
        assert len(matches) > 0
        match = matches[0]
        
        # Check that matched_components has expected keys
        assert "street" in match.matched_components
        assert "postal_code" in match.matched_components
        assert "city" in match.matched_components
        
        # Check types
        assert isinstance(match.matched_components["street"], bool)
        assert isinstance(match.matched_components["postal_code"], bool)
        assert isinstance(match.matched_components["city"], bool)
    
    def test_case_insensitive_matching(self, db_session: Session, test_user: User, test_properties: list):
        """Test that matching is case-insensitive"""
        matcher = AddressMatcher(db_session)
        
        # All lowercase
        matches_lower = matcher.match_address("hauptstrasse 123, 1010 wien", test_user.id)
        
        # All uppercase
        matches_upper = matcher.match_address("HAUPTSTRASSE 123, 1010 WIEN", test_user.id)
        
        # Mixed case
        matches_mixed = matcher.match_address("HaUpTsTrAsSe 123, 1010 WiEn", test_user.id)
        
        # All should return matches
        assert len(matches_lower) > 0
        assert len(matches_upper) > 0
        assert len(matches_mixed) > 0
