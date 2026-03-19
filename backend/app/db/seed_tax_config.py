"""Seed script for tax configurations (2022-2026)"""
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.tax_configuration import (
    TaxConfiguration,
    get_2022_tax_config,
    get_2023_tax_config,
    get_2024_tax_config,
    get_2025_tax_config,
    get_2026_tax_config,
)


def _seed_year(db: Session, config_data: dict):
    """Seed or update a single year's tax configuration."""
    year = config_data["tax_year"]
    existing = db.query(TaxConfiguration).filter(
        TaxConfiguration.tax_year == year
    ).first()

    if existing:
        print(f"  {year} config exists. Updating...")
        existing.tax_brackets = config_data["tax_brackets"]
        existing.exemption_amount = config_data["exemption_amount"]
        existing.vat_rates = config_data["vat_rates"]
        existing.svs_rates = config_data["svs_rates"]
        existing.deduction_config = config_data["deduction_config"]
    else:
        print(f"  Creating {year} config...")
        db.add(TaxConfiguration(**config_data))


def seed_tax_configs(db: Session = None):
    """
    Seed the database with all supported tax year configurations.

    Args:
        db: Database session (optional, will create one if not provided)
    """
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False

    try:
        for getter in (get_2022_tax_config, get_2023_tax_config, get_2024_tax_config, get_2025_tax_config, get_2026_tax_config):
            _seed_year(db, getter())

        db.commit()
        print("✓ Tax configurations seeded successfully!")

        # Display summary
        for row in db.query(TaxConfiguration).order_by(TaxConfiguration.tax_year).all():
            print(
                f"  Year {row.tax_year}: exemption €{row.exemption_amount:,.2f}, "
                f"{len(row.tax_brackets)} brackets"
            )

    except Exception as e:
        print(f"✗ Error seeding tax configuration: {e}")
        db.rollback()
        raise
    finally:
        if should_close:
            db.close()


# Keep backward-compatible alias
seed_2026_tax_config = seed_tax_configs


if __name__ == "__main__":
    seed_2026_tax_config()
