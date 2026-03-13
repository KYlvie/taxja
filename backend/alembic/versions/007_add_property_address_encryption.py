"""Add property address encryption support

Revision ID: 007
Revises: 006
Create Date: 2026-03-08 10:00:00.000000

This migration updates the properties table to support encrypted address fields.
The address, street, and city columns are increased in size to accommodate
encrypted data (which is larger than plaintext due to base64 encoding and nonce).

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Increase column sizes for encrypted address fields.
    
    Encrypted data is approximately 1.5x larger than plaintext due to:
    - Base64 encoding (33% overhead)
    - 12-byte nonce
    - 16-byte authentication tag
    
    Original sizes -> New sizes:
    - address: 500 -> 1000 characters
    - street: 255 -> 500 characters
    - city: 100 -> 200 characters
    """
    # Alter column types to accommodate encrypted data
    op.alter_column('properties', 'address',
                    existing_type=sa.String(length=500),
                    type_=sa.String(length=1000),
                    existing_nullable=False)
    
    op.alter_column('properties', 'street',
                    existing_type=sa.String(length=255),
                    type_=sa.String(length=500),
                    existing_nullable=False)
    
    op.alter_column('properties', 'city',
                    existing_type=sa.String(length=100),
                    type_=sa.String(length=200),
                    existing_nullable=False)


def downgrade() -> None:
    """
    Revert column sizes back to original values.
    
    WARNING: This will fail if any encrypted data exceeds the original column sizes.
    Ensure all data is decrypted before downgrading.
    """
    # Revert column types to original sizes
    op.alter_column('properties', 'address',
                    existing_type=sa.String(length=1000),
                    type_=sa.String(length=500),
                    existing_nullable=False)
    
    op.alter_column('properties', 'street',
                    existing_type=sa.String(length=500),
                    type_=sa.String(length=255),
                    existing_nullable=False)
    
    op.alter_column('properties', 'city',
                    existing_type=sa.String(length=200),
                    type_=sa.String(length=100),
                    existing_nullable=False)
