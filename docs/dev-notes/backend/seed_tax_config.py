"""Seed all tax configurations (2023–2026) after migration.

This is a convenience wrapper around the main seed function in app.db.seed_tax_config.
"""
import sys

from app.db.seed_tax_config import seed_tax_configs


if __name__ == "__main__":
    try:
        seed_tax_configs()
        sys.exit(0)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)
