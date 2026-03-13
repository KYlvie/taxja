"""Encrypt existing property addresses

Revision ID: 008
Revises: 007
Create Date: 2026-03-08 10:15:00.000000

This migration encrypts all existing property address data in the database.
It reads plaintext addresses, encrypts them, and updates the records.

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.core.encryption import get_encryption

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Encrypt all existing property addresses"""
    bind = op.get_bind()
    session = Session(bind=bind)
    encryption = get_encryption()
    
    # Get all properties
    result = session.execute(sa.text("SELECT id, address, street, city FROM properties"))
    properties = result.fetchall()
    
    # Encrypt each property's address fields
    for prop in properties:
        property_id, address, street, city = prop
        
        # Only encrypt if not already encrypted (check if it looks like base64)
        # Base64 strings are typically longer and contain only alphanumeric + / + = characters
        if address and not _looks_encrypted(address):
            encrypted_address = encryption.encrypt_field(address)
            encrypted_street = encryption.encrypt_field(street)
            encrypted_city = encryption.encrypt_field(city)
            
            session.execute(
                sa.text(
                    "UPDATE properties SET address = :address, street = :street, city = :city WHERE id = :id"
                ),
                {
                    "address": encrypted_address,
                    "street": encrypted_street,
                    "city": encrypted_city,
                    "id": property_id
                }
            )
    
    session.commit()


def downgrade() -> None:
    """Decrypt all property addresses back to plaintext"""
    bind = op.get_bind()
    session = Session(bind=bind)
    encryption = get_encryption()
    
    # Get all properties
    result = session.execute(sa.text("SELECT id, address, street, city FROM properties"))
    properties = result.fetchall()
    
    # Decrypt each property's address fields
    for prop in properties:
        property_id, address, street, city = prop
        
        # Only decrypt if encrypted (check if it looks like base64)
        if address and _looks_encrypted(address):
            try:
                decrypted_address = encryption.decrypt_field(address)
                decrypted_street = encryption.decrypt_field(street)
                decrypted_city = encryption.decrypt_field(city)
                
                session.execute(
                    sa.text(
                        "UPDATE properties SET address = :address, street = :street, city = :city WHERE id = :id"
                    ),
                    {
                        "address": decrypted_address,
                        "street": decrypted_street,
                        "city": decrypted_city,
                        "id": property_id
                    }
                )
            except Exception as e:
                # Log error but continue with other properties
                print(f"Error decrypting property {property_id}: {e}")
    
    session.commit()


def _looks_encrypted(value: str) -> bool:
    """
    Check if a string looks like it's already encrypted (base64 encoded).
    
    This is a heuristic check - base64 strings are typically:
    - Longer than plaintext (due to encoding overhead)
    - Contain only alphanumeric characters, +, /, and =
    - Have length that's a multiple of 4
    """
    if not value:
        return False
    
    # Check if it's significantly longer than typical addresses (encrypted data is ~1.5x larger)
    if len(value) < 50:
        return False
    
    # Check if it contains only base64 characters
    import re
    base64_pattern = re.compile(r'^[A-Za-z0-9+/]+=*$')
    return bool(base64_pattern.match(value))
