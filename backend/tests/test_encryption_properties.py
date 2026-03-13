"""Property-based tests for encryption/decryption module

**Validates: Requirements 17.1, 17.2**
- Requirement 17.1: Encrypt storage of all user data
- Requirement 17.2: Use AES_256 encryption for data at rest and TLS_1_3 for data in transit
"""
import os
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
from hypothesis import given, strategies as st, assume, settings
from app.core.encryption import DataEncryption


class TestEncryptionProperties:
    """Property-based tests for encryption/decryption roundtrip consistency"""
    
    @given(st.text(min_size=1, max_size=1000))
    @settings(max_examples=100)
    def test_property_17_encryption_decryption_roundtrip(self, plaintext: str):
        """
        **Validates: Requirements 17.1, 17.2**
        
        Property 17: Encryption/decryption roundtrip consistency
        
        For any valid string input, encrypting then decrypting should return the original data.
        This ensures data integrity through the encryption/decryption cycle.
        """
        # Create encryption instance with a random master key
        master_key = os.urandom(32)  # 256 bits for AES-256
        encryption = DataEncryption(master_key=master_key)
        
        # Encrypt the plaintext
        encrypted = encryption.encrypt(plaintext)
        
        # Decrypt the ciphertext
        decrypted = encryption.decrypt(encrypted)
        
        # Verify roundtrip consistency
        assert decrypted == plaintext, \
            f"Roundtrip failed: original != decrypted\nOriginal: {plaintext!r}\nDecrypted: {decrypted!r}"
    
    @given(st.text(min_size=1, max_size=1000))
    @settings(max_examples=100)
    def test_encrypted_data_differs_from_plaintext(self, plaintext: str):
        """
        **Validates: Requirements 17.1, 17.2**
        
        Property: Encrypted data should be different from original data
        
        This ensures that encryption actually transforms the data and doesn't
        just return the plaintext.
        """
        master_key = os.urandom(32)
        encryption = DataEncryption(master_key=master_key)
        
        encrypted = encryption.encrypt(plaintext)
        
        # Encrypted data should not equal plaintext
        assert encrypted != plaintext, \
            f"Encrypted data should differ from plaintext: {plaintext!r}"
    
    @given(st.text(min_size=1, max_size=1000))
    @settings(max_examples=50)
    def test_same_input_same_key_produces_different_output(self, plaintext: str):
        """
        **Validates: Requirements 17.1, 17.2**
        
        Property: Same input with same key produces different encrypted output
        
        AES-GCM uses a random nonce for each encryption, so even with the same
        key and plaintext, the encrypted output should be different each time.
        This prevents pattern analysis attacks.
        """
        master_key = os.urandom(32)
        encryption = DataEncryption(master_key=master_key)
        
        # Encrypt the same plaintext twice
        encrypted1 = encryption.encrypt(plaintext)
        encrypted2 = encryption.encrypt(plaintext)
        
        # The encrypted outputs should be different (due to random nonce)
        assert encrypted1 != encrypted2, \
            f"Same plaintext should produce different ciphertext due to random nonce"
        
        # But both should decrypt to the same plaintext
        decrypted1 = encryption.decrypt(encrypted1)
        decrypted2 = encryption.decrypt(encrypted2)
        
        assert decrypted1 == plaintext
        assert decrypted2 == plaintext
    
    @given(
        st.text(min_size=1, max_size=500),
        st.text(min_size=1, max_size=500)
    )
    @settings(max_examples=100)
    def test_different_inputs_produce_different_outputs(self, plaintext1: str, plaintext2: str):
        """
        **Validates: Requirements 17.1, 17.2**
        
        Property: Different inputs produce different encrypted outputs
        
        This ensures that the encryption function is injective (one-to-one)
        for different plaintexts.
        """
        # Skip if inputs are the same
        assume(plaintext1 != plaintext2)
        
        master_key = os.urandom(32)
        encryption = DataEncryption(master_key=master_key)
        
        encrypted1 = encryption.encrypt(plaintext1)
        encrypted2 = encryption.encrypt(plaintext2)
        
        # Different plaintexts should produce different ciphertexts
        assert encrypted1 != encrypted2, \
            f"Different plaintexts should produce different ciphertexts"
    
    @given(st.text(min_size=0, max_size=1000))
    @settings(max_examples=50)
    def test_empty_string_handling(self, plaintext: str):
        """
        **Validates: Requirements 17.1, 17.2**
        
        Property: Empty strings and edge cases are handled correctly
        
        The encryption should handle empty strings gracefully.
        """
        master_key = os.urandom(32)
        encryption = DataEncryption(master_key=master_key)
        
        encrypted = encryption.encrypt(plaintext)
        decrypted = encryption.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    @given(st.text(min_size=1, max_size=1000))
    @settings(max_examples=50)
    def test_different_keys_produce_different_outputs(self, plaintext: str):
        """
        **Validates: Requirements 17.1, 17.2**
        
        Property: Same plaintext with different keys produces different ciphertext
        
        This ensures that the encryption key is actually used in the encryption process.
        """
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        
        encryption1 = DataEncryption(master_key=key1)
        encryption2 = DataEncryption(master_key=key2)
        
        encrypted1 = encryption1.encrypt(plaintext)
        encrypted2 = encryption2.encrypt(plaintext)
        
        # Different keys should produce different ciphertexts
        assert encrypted1 != encrypted2, \
            f"Different keys should produce different ciphertexts"
        
        # Each should decrypt correctly with its own key
        assert encryption1.decrypt(encrypted1) == plaintext
        assert encryption2.decrypt(encrypted2) == plaintext
    
    @given(st.text(min_size=1, max_size=1000))
    @settings(max_examples=50)
    def test_wrong_key_cannot_decrypt(self, plaintext: str):
        """
        **Validates: Requirements 17.1, 17.2**
        
        Property: Data encrypted with one key cannot be decrypted with another key
        
        This ensures that the encryption provides confidentiality.
        """
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        
        encryption1 = DataEncryption(master_key=key1)
        encryption2 = DataEncryption(master_key=key2)
        
        encrypted = encryption1.encrypt(plaintext)
        
        # Attempting to decrypt with wrong key should raise an exception
        with pytest.raises(Exception):  # cryptography raises InvalidTag
            encryption2.decrypt(encrypted)
    
    @given(st.text(min_size=1, max_size=1000))
    @settings(max_examples=50)
    def test_field_encryption_with_none(self, plaintext: str):
        """
        **Validates: Requirements 17.1, 17.2**
        
        Property: Field encryption handles None values correctly
        
        The encrypt_field and decrypt_field methods should handle None values.
        """
        master_key = os.urandom(32)
        encryption = DataEncryption(master_key=master_key)
        
        # Test with actual value
        encrypted = encryption.encrypt_field(plaintext)
        decrypted = encryption.decrypt_field(encrypted)
        assert decrypted == plaintext
        
        # Test with None
        assert encryption.encrypt_field(None) is None
        assert encryption.decrypt_field(None) is None
    
    @given(
        st.text(min_size=1, max_size=100),
        st.text(min_size=1, max_size=100),
        st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=50)
    def test_multiple_field_encryption_independence(
        self,
        field1: str,
        field2: str,
        field3: str
    ):
        """
        **Validates: Requirements 17.1, 17.2**
        
        Property: Multiple field encryptions are independent
        
        Encrypting multiple fields should not affect each other's decryption.
        This simulates encrypting multiple user fields (tax_number, vat_number, address).
        """
        master_key = os.urandom(32)
        encryption = DataEncryption(master_key=master_key)
        
        # Encrypt multiple fields
        encrypted1 = encryption.encrypt(field1)
        encrypted2 = encryption.encrypt(field2)
        encrypted3 = encryption.encrypt(field3)
        
        # Decrypt in different order
        decrypted3 = encryption.decrypt(encrypted3)
        decrypted1 = encryption.decrypt(encrypted1)
        decrypted2 = encryption.decrypt(encrypted2)
        
        # All should decrypt correctly regardless of order
        assert decrypted1 == field1
        assert decrypted2 == field2
        assert decrypted3 == field3
