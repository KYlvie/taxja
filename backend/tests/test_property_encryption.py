"""Tests for property address encryption"""
import pytest
from uuid import uuid4
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.user import User
from app.core.encryption import get_encryption


class TestPropertyEncryption:
    """Test suite for property address field encryption"""
    
    def test_address_encryption_on_create(self, db: Session, test_user: User):
        """Test that address fields are encrypted when creating a property"""
        # Create property with plaintext address
        property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            address="Hauptstraße 123, 1010 Wien",
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 6, 15),
            purchase_price=Decimal("350000.00"),
            building_value=Decimal("280000.00"),
            depreciation_rate=Decimal("0.02")
        )
        
        db.add(property)
        db.flush()
        
        # Check that internal fields are encrypted (different from plaintext)
        assert property._address != "Hauptstraße 123, 1010 Wien"
        assert property._street != "Hauptstraße 123"
        assert property._city != "Wien"
        
        # Check that encrypted values are base64 strings
        assert len(property._address) > len("Hauptstraße 123, 1010 Wien")
        assert len(property._street) > len("Hauptstraße 123")
        assert len(property._city) > len("Wien")
        
        # Check that hybrid properties return decrypted values
        assert property.address == "Hauptstraße 123, 1010 Wien"
        assert property.street == "Hauptstraße 123"
        assert property.city == "Wien"
    
    def test_address_decryption_on_read(self, db: Session, test_user: User):
        """Test that address fields are decrypted when reading a property"""
        # Create and save property
        property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            address="Mariahilfer Straße 45",
            street="Mariahilfer Straße 45",
            city="Wien",
            postal_code="1060",
            purchase_date=date(2021, 3, 10),
            purchase_price=Decimal("450000.00"),
            building_value=Decimal("360000.00"),
            depreciation_rate=Decimal("0.02")
        )
        
        db.add(property)
        db.commit()
        property_id = property.id
        
        # Clear session to force fresh read from database
        db.expunge_all()
        
        # Read property from database
        retrieved_property = db.query(Property).filter(Property.id == property_id).first()
        
        # Verify decrypted values match original
        assert retrieved_property.address == "Mariahilfer Straße 45"
        assert retrieved_property.street == "Mariahilfer Straße 45"
        assert retrieved_property.city == "Wien"
        
        # Verify internal fields are still encrypted
        assert retrieved_property._address != "Mariahilfer Straße 45"
        assert retrieved_property._street != "Mariahilfer Straße 45"
        assert retrieved_property._city != "Wien"
    
    def test_address_update_encryption(self, db: Session, test_user: User):
        """Test that address fields are re-encrypted when updated"""
        # Create property
        property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            address="Alte Adresse 1",
            street="Alte Adresse 1",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            depreciation_rate=Decimal("0.02")
        )
        
        db.add(property)
        db.commit()
        
        # Store original encrypted values
        original_encrypted_address = property._address
        original_encrypted_street = property._street
        
        # Update address
        property.address = "Neue Adresse 2"
        property.street = "Neue Adresse 2"
        db.commit()
        
        # Verify encrypted values changed
        assert property._address != original_encrypted_address
        assert property._street != original_encrypted_street
        
        # Verify decrypted values are correct
        assert property.address == "Neue Adresse 2"
        assert property.street == "Neue Adresse 2"
    
    def test_null_address_handling(self, db: Session, test_user: User):
        """Test that None values are handled correctly"""
        encryption = get_encryption()
        
        # Test encrypt_field with None
        assert encryption.encrypt_field(None) is None
        
        # Test decrypt_field with None
        assert encryption.decrypt_field(None) is None
    
    def test_empty_string_encryption(self, db: Session):
        """Test that empty strings are handled correctly"""
        encryption = get_encryption()
        
        # Empty string should return empty string
        encrypted = encryption.encrypt("")
        assert encrypted == ""
        
        decrypted = encryption.decrypt("")
        assert decrypted == ""
    
    def test_encryption_roundtrip(self, db: Session):
        """Test that encryption and decryption are inverse operations"""
        encryption = get_encryption()
        
        test_addresses = [
            "Hauptstraße 123, 1010 Wien",
            "Mariahilfer Straße 45",
            "Stephansplatz 1",
            "Ringstraße 100, 1010 Wien, Österreich",
            "Kärtner Straße 51",  # Test with umlaut
        ]
        
        for address in test_addresses:
            encrypted = encryption.encrypt(address)
            decrypted = encryption.decrypt(encrypted)
            assert decrypted == address, f"Roundtrip failed for: {address}"
    
    def test_encrypted_data_is_different(self, db: Session):
        """Test that encrypted data is different from plaintext"""
        encryption = get_encryption()
        
        plaintext = "Hauptstraße 123"
        encrypted = encryption.encrypt(plaintext)
        
        # Encrypted should be different from plaintext
        assert encrypted != plaintext
        
        # Encrypted should be longer (base64 + nonce + tag)
        assert len(encrypted) > len(plaintext)
    
    def test_same_plaintext_different_ciphertext(self, db: Session):
        """Test that encrypting the same plaintext twice produces different ciphertext (due to random nonce)"""
        encryption = get_encryption()
        
        plaintext = "Hauptstraße 123"
        encrypted1 = encryption.encrypt(plaintext)
        encrypted2 = encryption.encrypt(plaintext)
        
        # Different ciphertexts due to random nonce
        assert encrypted1 != encrypted2
        
        # But both decrypt to same plaintext
        assert encryption.decrypt(encrypted1) == plaintext
        assert encryption.decrypt(encrypted2) == plaintext
    
    def test_property_repr_with_encrypted_address(self, db: Session, test_user: User):
        """Test that __repr__ works correctly with encrypted addresses"""
        property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            address="Teststraße 1",
            street="Teststraße 1",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            depreciation_rate=Decimal("0.02")
        )
        
        db.add(property)
        db.flush()
        
        # __repr__ should show decrypted address
        repr_str = repr(property)
        assert "Teststraße 1" in repr_str
        assert property.status.value in repr_str


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user"""
    user = User(
        email="test@example.com",
        name="Test User",
        hashed_password="hashed_password",
        user_type="landlord"
    )
    db.add(user)
    db.commit()
    return user
