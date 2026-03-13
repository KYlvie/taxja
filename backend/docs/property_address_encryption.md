# Property Address Encryption

## Overview

Property address fields (address, street, city) are encrypted at rest in the database using AES-256-GCM encryption to comply with GDPR requirements and protect sensitive user data.

## Implementation

### Encryption Method

- **Algorithm**: AES-256-GCM (Galois/Counter Mode)
- **Key Size**: 256 bits (32 bytes)
- **Nonce**: 96 bits (12 bytes), randomly generated per encryption
- **Authentication**: Built-in authentication tag (16 bytes)
- **Encoding**: Base64 for storage

### Encrypted Fields

The following Property model fields are encrypted:
- `address` - Full address string
- `street` - Street address
- `city` - City name

Note: `postal_code` is NOT encrypted as it's needed for queries and has low sensitivity.

### Database Schema

Encrypted fields require larger column sizes to accommodate:
- Base64 encoding overhead (~33%)
- 12-byte nonce
- 16-byte authentication tag

Column sizes:
- `address`: 1000 characters (was 500)
- `street`: 500 characters (was 255)
- `city`: 200 characters (was 100)

## Usage

### Creating Properties

Encryption is transparent when using the Property model:

```python
from app.models.property import Property
from datetime import date
from decimal import Decimal

# Create property with plaintext addresses
property = Property(
    user_id=user.id,
    address="Hauptstraße 123, 1010 Wien",
    street="Hauptstraße 123",
    city="Wien",
    postal_code="1010",
    purchase_date=date(2020, 6, 15),
    purchase_price=Decimal("350000.00"),
    building_value=Decimal("280000.00")
)

db.add(property)
db.commit()

# Address is automatically encrypted in database
# But reads as plaintext through the model
print(property.address)  # "Hauptstraße 123, 1010 Wien"
```

### Reading Properties

Decryption is automatic when accessing properties:

```python
# Query property
property = db.query(Property).filter(Property.id == property_id).first()

# Access decrypted values
print(property.address)  # Plaintext
print(property.street)   # Plaintext
print(property.city)     # Plaintext

# Internal encrypted values (don't use these directly)
print(property._address)  # Base64 encrypted string
```

### Updating Properties

Updates are automatically re-encrypted:

```python
property = db.query(Property).filter(Property.id == property_id).first()

# Update address (will be re-encrypted)
property.address = "Neue Straße 456"
property.street = "Neue Straße 456"

db.commit()
```

## Hybrid Properties

The Property model uses SQLAlchemy hybrid properties to provide transparent encryption/decryption:

```python
@hybrid_property
def address(self) -> Optional[str]:
    """Decrypt address field"""
    if self._address:
        return get_encryption().decrypt_field(self._address)
    return None

@address.setter
def address(self, value: Optional[str]) -> None:
    """Encrypt address field"""
    if value:
        self._address = get_encryption().encrypt_field(value)
    else:
        self._address = None
```

## Migrations

### Schema Migration (007)

Increases column sizes to accommodate encrypted data:

```bash
# Apply migration
alembic upgrade head
```

### Data Migration (008)

Encrypts existing plaintext addresses:

```bash
# This runs automatically with upgrade
alembic upgrade head
```

To rollback (decrypt data):

```bash
alembic downgrade -1
```

## Security Considerations

### Key Management

- Encryption key is stored in environment variable `ENCRYPTION_KEY`
- Key must be 32 bytes (256 bits), base64-encoded
- Never commit keys to version control
- Rotate keys periodically (requires re-encryption of all data)

### Key Generation

Generate a new encryption key:

```python
import os
import base64

# Generate 32 random bytes
key = os.urandom(32)

# Encode as base64 for storage in .env
key_b64 = base64.b64encode(key).decode('utf-8')
print(f"ENCRYPTION_KEY={key_b64}")
```

### Nonce Uniqueness

- Each encryption operation uses a fresh random nonce
- This ensures the same plaintext produces different ciphertext
- Prevents pattern analysis attacks

### Authentication

- AES-GCM provides built-in authentication
- Detects tampering or corruption
- Decryption fails if data is modified

## Performance

### Encryption Overhead

- Encryption/decryption adds ~1-2ms per operation
- Negligible for typical property operations
- Consider caching for high-frequency reads

### Storage Overhead

- Encrypted data is ~1.5x larger than plaintext
- Base64 encoding: +33%
- Nonce: +12 bytes
- Auth tag: +16 bytes

### Query Limitations

- Cannot query encrypted fields directly (e.g., `WHERE address LIKE '%Wien%'`)
- Use postal_code for location-based queries
- Consider full-text search on decrypted data if needed

## Testing

Run encryption tests:

```bash
pytest backend/tests/test_property_encryption.py -v
```

Test coverage includes:
- Encryption on create
- Decryption on read
- Re-encryption on update
- Null value handling
- Empty string handling
- Roundtrip verification
- Nonce randomness

## Troubleshooting

### Decryption Errors

If you see decryption errors:

1. Check that `ENCRYPTION_KEY` is set correctly
2. Verify key hasn't changed (would invalidate all encrypted data)
3. Check for database corruption

### Migration Issues

If migration fails:

1. Backup database before running migrations
2. Check that column sizes are sufficient
3. Verify no data loss during migration

### Key Rotation

To rotate encryption keys:

1. Decrypt all data with old key
2. Update `ENCRYPTION_KEY` environment variable
3. Re-encrypt all data with new key

```python
# Key rotation script (run with caution)
from app.core.encryption import DataEncryption
from app.models.property import Property

old_encryption = DataEncryption(old_key)
new_encryption = DataEncryption(new_key)

properties = db.query(Property).all()
for prop in properties:
    # Decrypt with old key
    address = old_encryption.decrypt(prop._address)
    street = old_encryption.decrypt(prop._street)
    city = old_encryption.decrypt(prop._city)
    
    # Re-encrypt with new key
    prop._address = new_encryption.encrypt(address)
    prop._street = new_encryption.encrypt(street)
    prop._city = new_encryption.encrypt(city)

db.commit()
```

## Compliance

### GDPR

- Encryption at rest protects personal data
- Supports right to erasure (delete encrypted data)
- Supports data portability (decrypt for export)

### Audit Trail

- All property operations are logged
- Encryption/decryption is transparent to audit logs
- Logs show plaintext addresses (ensure log security)

## References

- [AES-GCM Specification](https://csrc.nist.gov/publications/detail/sp/800-38d/final)
- [GDPR Article 32 - Security of Processing](https://gdpr-info.eu/art-32-gdpr/)
- [SQLAlchemy Hybrid Attributes](https://docs.sqlalchemy.org/en/20/orm/extensions/hybrid.html)
