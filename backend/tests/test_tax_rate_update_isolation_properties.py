"""
Property-Based Tests for Tax Rate Update Isolation

Property 20: Tax rate updates don't affect historical data

Validates Requirements 13.3, 13.4:
- Tax rate updates only affect current and future years
- Historical calculations remain unchanged
"""

import pytest
from decimal import Decimal
from datetime import datetime, date
from hypothesis import given, strategies as st, assume, settings
from sqlalchemy.orm import Session

from app.models.user import User, UserType
from app.models.transaction import Transaction, TransactionType, IncomeCategory
from app.models.tax_configuration import TaxConfiguration
from app.models.tax_report import TaxReport
from app.services.tax_rate_update_service import TaxRateUpdateService
from app.services.tax_calculation_engine import TaxCalculationEngine


# Strategies
@st.composite
def tax_year_strategy(draw):
    """Generate valid tax years"""
    return draw(st.integers(min_value=2020, max_value=2030))


@st.composite
def income_amount_strategy(draw):
    """Generate realistic income amounts"""
    return Decimal(str(draw(st.floats(min_value=10000, max_value=200000, allow_nan=False))))


@st.composite
def tax_rate_strategy(draw):
    """Generate valid tax rates (0-1)"""
    return Decimal(str(draw(st.floats(min_value=0.0, max_value=0.6, allow_nan=False))))


class TestTaxRateUpdateIsolation:
    """Test that tax rate updates don't affect historical data"""
    
    @given(
        base_year=tax_year_strategy(),
        income=income_amount_strategy(),
        new_rate=tax_rate_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_historical_calculation_unchanged_after_rate_update(
        self,
        db_session: Session,
        base_year: int,
        income: Decimal,
        new_rate: Decimal
    ):
        """
        Property: Updating tax rates for year Y+1 does not change
        tax calculations for year Y.
        
        Given:
        - A tax configuration for year Y
        - A transaction and tax calculation for year Y
        - An update to tax rates for year Y+1
        
        Then:
        - Recalculating taxes for year Y produces the same result
        """
        # Create user
        user = User(
            email=f"test_{base_year}@example.com",
            hashed_password="hashed",
            user_type=UserType.EMPLOYEE,
            is_active=True
        )
        db_session.add(user)
        db_session.flush()
        
        # Create tax configuration for base year
        base_config = self._create_tax_config(db_session, base_year)
        
        # Create transaction for base year
        transaction = Transaction(
            user_id=user.id,
            type=TransactionType.INCOME,
            income_category=IncomeCategory.EMPLOYMENT,
            amount=income,
            date=date(base_year, 6, 15),
            description="Salary",
            tax_year=base_year
        )
        db_session.add(transaction)
        db_session.flush()
        
        # Calculate tax for base year (original calculation)
        engine = TaxCalculationEngine(db_session)
        original_result = engine.calculate_income_tax(
            user_id=user.id,
            tax_year=base_year
        )
        original_tax = original_result.total_tax
        
        # Create tax report to store original calculation
        original_report = TaxReport(
            user_id=user.id,
            tax_year=base_year,
            total_income=income,
            total_tax=original_tax,
            generated_at=datetime.utcnow()
        )
        db_session.add(original_report)
        db_session.commit()
        
        # Update tax rates for next year
        next_year = base_year + 1
        update_service = TaxRateUpdateService(db_session)
        
        # Create config for next year
        next_config = update_service.create_new_year_config(
            tax_year=next_year,
            template_year=base_year
        )
        
        # Modify tax rates for next year
        update_service.update_tax_config(
            tax_year=next_year,
            updates={
                'exemption_amount': base_config.exemption_amount * Decimal('1.1'),
                'tax_brackets': [
                    {
                        'lower_limit': 0,
                        'upper_limit': 15000,
                        'rate': float(new_rate)
                    },
                    {
                        'lower_limit': 15000,
                        'upper_limit': 999999999,
                        'rate': float(new_rate * Decimal('1.5'))
                    }
                ]
            }
        )
        
        # Recalculate tax for base year (should be unchanged)
        recalculated_result = engine.calculate_income_tax(
            user_id=user.id,
            tax_year=base_year
        )
        recalculated_tax = recalculated_result.total_tax
        
        # Property: Historical calculation unchanged
        assert recalculated_tax == original_tax, (
            f"Tax calculation for year {base_year} changed after updating year {next_year}. "
            f"Original: €{original_tax}, Recalculated: €{recalculated_tax}"
        )
        
        # Verify stored report unchanged
        stored_report = db_session.query(TaxReport).filter(
            TaxReport.id == original_report.id
        ).first()
        assert stored_report.total_tax == original_tax
    
    @given(
        base_year=tax_year_strategy(),
        income=income_amount_strategy()
    )
    @settings(max_examples=30, deadline=None)
    def test_multiple_year_updates_preserve_history(
        self,
        db_session: Session,
        base_year: int,
        income: Decimal
    ):
        """
        Property: Multiple sequential tax rate updates preserve
        all historical calculations.
        
        Given:
        - Tax configurations for years Y, Y+1, Y+2
        - Transactions for each year
        - Sequential updates to each year's rates
        
        Then:
        - Each year's calculation remains independent
        """
        user = User(
            email=f"multi_{base_year}@example.com",
            hashed_password="hashed",
            user_type=UserType.EMPLOYEE,
            is_active=True
        )
        db_session.add(user)
        db_session.flush()
        
        # Create configurations and transactions for 3 years
        years = [base_year, base_year + 1, base_year + 2]
        original_taxes = {}
        
        for year in years:
            # Create config
            self._create_tax_config(db_session, year)
            
            # Create transaction
            transaction = Transaction(
                user_id=user.id,
                type=TransactionType.INCOME,
                income_category=IncomeCategory.EMPLOYMENT,
                amount=income,
                date=date(year, 6, 15),
                description=f"Salary {year}",
                tax_year=year
            )
            db_session.add(transaction)
            db_session.flush()
            
            # Calculate and store original tax
            engine = TaxCalculationEngine(db_session)
            result = engine.calculate_income_tax(user_id=user.id, tax_year=year)
            original_taxes[year] = result.total_tax
        
        db_session.commit()
        
        # Update tax rates for middle year
        update_service = TaxRateUpdateService(db_session)
        update_service.update_tax_config(
            tax_year=base_year + 1,
            updates={'exemption_amount': Decimal('20000')}
        )
        
        # Recalculate all years
        engine = TaxCalculationEngine(db_session)
        for year in years:
            recalculated = engine.calculate_income_tax(user_id=user.id, tax_year=year)
            
            # Property: Only the updated year should potentially differ
            # (but in this case, exemption change might not affect all incomes)
            # The key is that other years are NOT affected
            if year != base_year + 1:
                assert recalculated.total_tax == original_taxes[year], (
                    f"Tax for year {year} changed after updating year {base_year + 1}"
                )
    
    @given(
        year=tax_year_strategy(),
        income=income_amount_strategy()
    )
    @settings(max_examples=30, deadline=None)
    def test_config_isolation_by_year(
        self,
        db_session: Session,
        year: int,
        income: Decimal
    ):
        """
        Property: Each year's tax configuration is isolated.
        
        Given:
        - Different tax configurations for different years
        
        Then:
        - Calculations use the correct year's configuration
        - Configurations don't interfere with each other
        """
        user = User(
            email=f"isolation_{year}@example.com",
            hashed_password="hashed",
            user_type=UserType.EMPLOYEE,
            is_active=True
        )
        db_session.add(user)
        db_session.flush()
        
        # Create two different configurations
        config_year1 = self._create_tax_config(
            db_session,
            year,
            exemption=Decimal('10000')
        )
        config_year2 = self._create_tax_config(
            db_session,
            year + 1,
            exemption=Decimal('20000')
        )
        
        # Create transactions for both years
        txn1 = Transaction(
            user_id=user.id,
            type=TransactionType.INCOME,
            income_category=IncomeCategory.EMPLOYMENT,
            amount=income,
            date=date(year, 6, 15),
            description="Year 1",
            tax_year=year
        )
        txn2 = Transaction(
            user_id=user.id,
            type=TransactionType.INCOME,
            income_category=IncomeCategory.EMPLOYMENT,
            amount=income,
            date=date(year + 1, 6, 15),
            description="Year 2",
            tax_year=year + 1
        )
        db_session.add_all([txn1, txn2])
        db_session.commit()
        
        # Calculate taxes
        engine = TaxCalculationEngine(db_session)
        result1 = engine.calculate_income_tax(user_id=user.id, tax_year=year)
        result2 = engine.calculate_income_tax(user_id=user.id, tax_year=year + 1)
        
        # Property: Different exemptions should produce different results
        # (assuming income is above both exemption amounts)
        if income > Decimal('20000'):
            assert result1.total_tax != result2.total_tax, (
                "Different tax configurations should produce different results"
            )
    
    def _create_tax_config(
        self,
        db: Session,
        year: int,
        exemption: Decimal = Decimal('13539')
    ) -> TaxConfiguration:
        """Helper to create a tax configuration"""
        config = TaxConfiguration(
            tax_year=year,
            exemption_amount=exemption,
            tax_brackets=[
                {"lower": 0, "upper": 13539, "rate": 0.00},
                {"lower": 13539, "upper": 21992, "rate": 0.20},
                {"lower": 21992, "upper": 36458, "rate": 0.30},
                {"lower": 36458, "upper": 999999999, "rate": 0.40},
            ],
            vat_rates={
                "standard": 0.20,
                "residential": 0.10,
                "small_business_threshold": 55000.00,
                "tolerance_threshold": 60500.00,
            },
            svs_rates={
                "pension": 0.185,
                "health": 0.068,
                "accident_fixed": 12.95,
                "supplementary_pension": 0.0153,
                "gsvg_min_base_monthly": 551.10,
                "gsvg_min_income_yearly": 6613.20,
                "neue_min_monthly": 160.81,
                "max_base_monthly": 8085.00,
            },
            deduction_config={
                "home_office": 300.00,
                "child_deduction_monthly": 58.40,
                "single_parent_deduction": 494.00,
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        return config


@pytest.fixture
def db_session():
    """Provide a test database session"""
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()
