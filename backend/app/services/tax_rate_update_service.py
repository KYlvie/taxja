"""
Tax Rate Update Service

Handles creation and updating of tax configurations for new years.
Validates tax bracket continuity and rate progression.
"""

from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.tax_configuration import TaxConfiguration
from app.schemas.tax_configuration import TaxConfigurationCreate, TaxBracketCreate


class TaxRateUpdateService:
    """Service for managing tax rate updates across years"""

    def __init__(self, db: Session):
        self.db = db

    def create_new_year_config(
        self,
        tax_year: int,
        template_year: Optional[int] = None
    ) -> TaxConfiguration:
        """
        Create new tax configuration for a year.

        Args:
            tax_year: Year for new configuration
            template_year: Year to copy from (defaults to previous year)

        Returns:
            New TaxConfiguration instance

        Raises:
            ValueError: If configuration already exists or template not found
        """
        # Check if configuration already exists
        existing = self.db.query(TaxConfiguration).filter(
            TaxConfiguration.tax_year == tax_year
        ).first()

        if existing:
            raise ValueError(f"Tax configuration for year {tax_year} already exists")

        # Get template configuration
        if template_year is None:
            template_year = tax_year - 1

        template = self.db.query(TaxConfiguration).filter(
            TaxConfiguration.tax_year == template_year
        ).first()

        if not template:
            raise ValueError(f"Template configuration for year {template_year} not found")

        # Create new configuration based on template (JSON-based model)
        new_config = TaxConfiguration(
            tax_year=tax_year,
            exemption_amount=template.exemption_amount,
            tax_brackets=list(template.tax_brackets),  # copy JSON list
            vat_rates=dict(template.vat_rates),
            svs_rates=dict(template.svs_rates),
            deduction_config=dict(template.deduction_config),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        self.db.add(new_config)
        self.db.commit()
        self.db.refresh(new_config)

        return new_config

    def update_tax_config(
        self,
        tax_year: int,
        updates: Dict
    ) -> TaxConfiguration:
        """
        Update existing tax configuration.

        Args:
            tax_year: Year to update
            updates: Dictionary of fields to update

        Returns:
            Updated TaxConfiguration

        Raises:
            ValueError: If configuration not found or validation fails
        """
        config = self.db.query(TaxConfiguration).filter(
            TaxConfiguration.tax_year == tax_year
        ).first()

        if not config:
            raise ValueError(f"Tax configuration for year {tax_year} not found")

        # Update fields
        for field, value in updates.items():
            if hasattr(config, field):
                setattr(config, field, value)

        config.updated_at = datetime.utcnow()

        # Validate tax brackets if updated
        if 'tax_brackets' in updates:
            self.validate_tax_brackets(config.tax_brackets)

        self.db.commit()
        self.db.refresh(config)

        return config

    def validate_tax_brackets(self, brackets: List[Dict]) -> bool:
        """
        Validate tax bracket continuity and rate progression.

        Args:
            brackets: List of tax bracket dicts with 'lower', 'upper', 'rate' keys

        Returns:
            True if valid

        Raises:
            ValueError: If validation fails
        """
        if not brackets:
            raise ValueError("Tax brackets cannot be empty")

        # Sort brackets by lower limit
        sorted_brackets = sorted(brackets, key=lambda b: b['lower'])

        # Check first bracket starts at 0
        if Decimal(str(sorted_brackets[0]['lower'])) != Decimal('0'):
            raise ValueError("First tax bracket must start at €0")

        # Check continuity and rate progression
        for i in range(len(sorted_brackets) - 1):
            current = sorted_brackets[i]
            next_bracket = sorted_brackets[i + 1]

            current_upper = Decimal(str(current['upper'])) if current['upper'] is not None else None
            next_lower = Decimal(str(next_bracket['lower']))

            # Check continuity (no gaps)
            if current_upper is not None and current_upper != next_lower:
                raise ValueError(
                    f"Gap in tax brackets: bracket {i} ends at €{current_upper}, "
                    f"but bracket {i+1} starts at €{next_lower}"
                )

            # Check rate progression (rates should increase or stay same)
            current_rate = Decimal(str(current['rate']))
            next_rate = Decimal(str(next_bracket['rate']))
            if next_rate < current_rate:
                raise ValueError(
                    f"Tax rate regression: bracket {i} has rate {current_rate * 100}%, "
                    f"but bracket {i+1} has lower rate {next_rate * 100}%"
                )

        # Check all rates are between 0 and 1
        for bracket in sorted_brackets:
            rate = Decimal(str(bracket['rate']))
            if not (Decimal('0') <= rate <= Decimal('1')):
                raise ValueError(
                    f"Invalid tax rate: {rate * 100}% must be between 0% and 100%"
                )

        return True

    def get_config_for_year(self, tax_year: int) -> Optional[TaxConfiguration]:
        """Get tax configuration for a specific year"""
        return self.db.query(TaxConfiguration).filter(
            TaxConfiguration.tax_year == tax_year
        ).first()

    def list_all_configs(self) -> List[TaxConfiguration]:
        """List all tax configurations ordered by year"""
        return self.db.query(TaxConfiguration).order_by(
            TaxConfiguration.tax_year.desc()
        ).all()
