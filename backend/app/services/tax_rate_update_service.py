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
        
        # Create new configuration based on template
        new_config = TaxConfiguration(
            tax_year=tax_year,
            exemption_amount=template.exemption_amount,
            vat_standard_rate=template.vat_standard_rate,
            vat_residential_rate=template.vat_residential_rate,
            vat_small_business_threshold=template.vat_small_business_threshold,
            vat_tolerance_threshold=template.vat_tolerance_threshold,
            svs_pension_rate=template.svs_pension_rate,
            svs_health_rate=template.svs_health_rate,
            svs_accident_fixed=template.svs_accident_fixed,
            svs_supplementary_rate=template.svs_supplementary_rate,
            svs_gsvg_min_base_monthly=template.svs_gsvg_min_base_monthly,
            svs_gsvg_min_income_yearly=template.svs_gsvg_min_income_yearly,
            svs_neue_min_monthly=template.svs_neue_min_monthly,
            svs_max_base_monthly=template.svs_max_base_monthly,
            commuting_allowance_config=template.commuting_allowance_config,
            home_office_deduction=template.home_office_deduction,
            child_deduction_monthly=template.child_deduction_monthly,
            single_parent_deduction=template.single_parent_deduction,
            deduction_config=template.deduction_config,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.db.add(new_config)
        self.db.flush()
        
        # Copy tax brackets
        for bracket in template.tax_brackets:
            new_bracket = TaxBracket(
                tax_configuration_id=new_config.id,
                lower_limit=bracket.lower_limit,
                upper_limit=bracket.upper_limit,
                rate=bracket.rate,
                order=bracket.order
            )
            self.db.add(new_bracket)
        
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
            if field == 'tax_brackets':
                # Handle tax brackets separately
                self._update_tax_brackets(config, value)
            elif hasattr(config, field):
                setattr(config, field, value)
        
        config.updated_at = datetime.utcnow()
        
        # Validate before committing
        if 'tax_brackets' in updates:
            self.validate_tax_brackets(config.tax_brackets)
        
        self.db.commit()
        self.db.refresh(config)
        
        return config
    
    def _update_tax_brackets(
        self,
        config: TaxConfiguration,
        brackets_data: List[Dict]
    ):
        """Update tax brackets for a configuration"""
        # Delete existing brackets
        for bracket in config.tax_brackets:
            self.db.delete(bracket)
        
        # Create new brackets
        for idx, bracket_data in enumerate(brackets_data):
            new_bracket = TaxBracket(
                tax_configuration_id=config.id,
                lower_limit=Decimal(str(bracket_data['lower_limit'])),
                upper_limit=Decimal(str(bracket_data['upper_limit'])),
                rate=Decimal(str(bracket_data['rate'])),
                order=idx
            )
            self.db.add(new_bracket)
    
    def validate_tax_brackets(self, brackets: List[TaxBracket]) -> bool:
        """
        Validate tax bracket continuity and rate progression.
        
        Args:
            brackets: List of tax brackets to validate
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If validation fails
        """
        if not brackets:
            raise ValueError("Tax brackets cannot be empty")
        
        # Sort brackets by order
        sorted_brackets = sorted(brackets, key=lambda b: b.order)
        
        # Check first bracket starts at 0
        if sorted_brackets[0].lower_limit != Decimal('0'):
            raise ValueError("First tax bracket must start at €0")
        
        # Check continuity and rate progression
        for i in range(len(sorted_brackets) - 1):
            current = sorted_brackets[i]
            next_bracket = sorted_brackets[i + 1]
            
            # Check continuity (no gaps)
            if current.upper_limit != next_bracket.lower_limit:
                raise ValueError(
                    f"Gap in tax brackets: bracket {i} ends at €{current.upper_limit}, "
                    f"but bracket {i+1} starts at €{next_bracket.lower_limit}"
                )
            
            # Check rate progression (rates should increase or stay same)
            if next_bracket.rate < current.rate:
                raise ValueError(
                    f"Tax rate regression: bracket {i} has rate {current.rate * 100}%, "
                    f"but bracket {i+1} has lower rate {next_bracket.rate * 100}%"
                )
        
        # Check all rates are between 0 and 1
        for bracket in sorted_brackets:
            if not (Decimal('0') <= bracket.rate <= Decimal('1')):
                raise ValueError(
                    f"Invalid tax rate: {bracket.rate * 100}% must be between 0% and 100%"
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
