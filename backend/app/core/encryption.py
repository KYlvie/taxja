"""Data encryption utilities using AES-256-GCM"""
import base64
import os
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from app.core.config import settings


class DataEncryption:
    """AES-256-GCM encryption for sensitive data"""
    
    def __init__(self, master_key: Optional[bytes] = None):
        """Initialize encryption with master key"""
        if master_key is None:
            # Get key from settings and decode from base64
            master_key = base64.b64decode(settings.ENCRYPTION_KEY)
        
        if len(master_key) != 32:  # 256 bits
            raise ValueError("Master key must be 32 bytes (256 bits)")
        
        self.aesgcm = AESGCM(master_key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64-encoded string containing nonce + ciphertext
        """
        if not plaintext:
            return ""
        
        # Generate random nonce (96 bits)
        nonce = os.urandom(12)
        
        # Encrypt
        ciphertext = self.aesgcm.encrypt(
            nonce,
            plaintext.encode('utf-8'),
            None  # No additional authenticated data
        )
        
        # Combine nonce + ciphertext and encode as base64
        encrypted_data = nonce + ciphertext
        return base64.b64encode(encrypted_data).decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt encrypted string
        
        Args:
            encrypted_data: Base64-encoded string containing nonce + ciphertext
            
        Returns:
            Decrypted plaintext string
        """
        if not encrypted_data:
            return ""
        
        # Decode from base64
        data = base64.b64decode(encrypted_data)
        
        # Extract nonce (first 12 bytes) and ciphertext
        nonce = data[:12]
        ciphertext = data[12:]
        
        # Decrypt
        plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
    
    def encrypt_field(self, value: Optional[str]) -> Optional[str]:
        """Encrypt a field value, handling None"""
        if value is None:
            return None
        return self.encrypt(value)
    
    def decrypt_field(self, value: Optional[str]) -> Optional[str]:
        """Decrypt a field value, handling None"""
        if value is None:
            return None
        return self.decrypt(value)


# Global encryption instance (lazy initialization)
_encryption_instance = None


def get_encryption() -> DataEncryption:
    """Get or create the global encryption instance"""
    global _encryption_instance
    if _encryption_instance is None:
        _encryption_instance = DataEncryption()
    return _encryption_instance


def encrypt_user_fields(user_data: dict) -> dict:
    """
    Encrypt sensitive user fields
    
    Args:
        user_data: Dictionary containing user data
        
    Returns:
        Dictionary with encrypted sensitive fields
    """
    encrypted_fields = ['tax_number', 'vat_number', 'address', 'two_factor_secret']
    encryption = get_encryption()
    
    result = user_data.copy()
    for field in encrypted_fields:
        if field in result and result[field]:
            result[field] = encryption.encrypt_field(result[field])
    
    return result


def decrypt_user_fields(user_data: dict) -> dict:
    """
    Decrypt sensitive user fields
    
    Args:
        user_data: Dictionary containing encrypted user data
        
    Returns:
        Dictionary with decrypted sensitive fields
    """
    encrypted_fields = ['tax_number', 'vat_number', 'address', 'two_factor_secret']
    encryption = get_encryption()
    
    result = user_data.copy()
    for field in encrypted_fields:
        if field in result and result[field]:
            result[field] = encryption.decrypt_field(result[field])
    
    return result


def encrypt_property_fields(property_data: dict) -> dict:
    """
    Encrypt sensitive property fields
    
    Args:
        property_data: Dictionary containing property data
        
    Returns:
        Dictionary with encrypted sensitive fields
    """
    encrypted_fields = ['address', 'street', 'city']
    encryption = get_encryption()
    
    result = property_data.copy()
    for field in encrypted_fields:
        if field in result and result[field]:
            result[field] = encryption.encrypt_field(result[field])
    
    return result


def decrypt_property_fields(property_data: dict) -> dict:
    """
    Decrypt sensitive property fields
    
    Args:
        property_data: Dictionary containing encrypted property data
        
    Returns:
        Dictionary with decrypted sensitive fields
    """
    encrypted_fields = ['address', 'street', 'city']
    encryption = get_encryption()
    
    result = property_data.copy()
    for field in encrypted_fields:
        if field in result and result[field]:
            result[field] = encryption.decrypt_field(result[field])
    
    return result
