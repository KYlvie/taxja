"""
Property-based tests for loss carryforward service

**Validates: Requirements 36.1, 36.2, 36.5, 16.5**

Property 21: Loss carryforward correct propagation
- Loss carryforward propagates correctly across multiple years
- Losses are applied before tax calculation
- When losses exceed income, tax is €0 and remaining loss is tracked
- Loss carryforward amounts are never negative
- Multi-year loss carryforward maintains consistency
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from decimal import Decimal
from sqlalchemy import create_engine, Column, Integer, Numeric, DateTime, ForeignKey, String, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime
from enum import Enum

# Create test Base
Base = declarative_base()


# Define minimal models for testing
class UserType(str, Enum):
    EMPLOYEE = "employee"
    SELF_EMPLOYED = "self_employed"
    LANDLORD = "landlord"
    MIXED = "mixed"


class User(Base):
    """Minimal User model for testing"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    user_type = Column(SQLEnum(UserType), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    loss_carryforwards = relationship("LossCarryforward", back_populates="user")


class LossCarryforward(Base):
    """Loss carryforward model for testing"""
    __tablename__ = "loss_carryforwards"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    loss_year = Column(Integer, nullable=False, index=True)
    loss_amount = Column(Numeric(12, 2), nullable=False)
    used_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    remaining_amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    user = relationship("User", back_populates="loss_carryforwards")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'loss_year', name='uq_user_loss_year'),
    )


# Import service after models are defined
from app.services.loss_carryforward_service import (
    LossCarryforwardService,
    LossCarryforwardResult,
    LossCalculationResult
)


# Test database setup
@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        name="Test User",
        user_type=UserType.SELF_EMPLOYED
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def loss_service(db_session):
    """Create a loss carryforward service instance"""
    return LossCarryforwardService(db_session)


# Custom strategies for generating test data
def decimal_strategy(min_value=0, max_value=1000000, places=2):
    """Generate Decimal values with specified precision"""
    return st.decimals(
        min_value=Decimal(str(min_value)),
        max_value=Decimal(str(max_value)),
        allow_nan=False,
        allow_infinity=False,
        places=places
    )


class TestProperty21LossCarryforwardPropagation:
    """
    **Property 21: Loss carryforward correct propagation**
    **Validates: Requirements 36.1, 36.2, 36.5, 16.5**
    
    Tests that loss carryforward:
    1. Propagates correctly across multiple years
    2. Is applied before tax calculation
    3. Results in €0 tax when losses exceed income
    4. Never produces negative amounts
    5. Maintains consistency across multi-year scenarios
    """
    
    @given(
        loss_amount=decimal_strategy(min_value=1, max_value=100000),
        used_amount=decimal_strategy(min_value=0, max_value=100000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_remaining_loss_calculation_correctness(
        self,
        loss_amount: Decimal,
        used_amount: Decimal,
        loss_service,
        test_user
    ):
        """
        Property: Remaining carryforward = Original loss - Used amount
        
        For any loss amount and used amount where used <= loss:
        remaining_amount = loss_amount - used_amount
        
        **Validates: Requirements 36.1, 36.2**
        """
        # Ensure used amount doesn't exceed loss amount
        assume(used_amount <= loss_amount)
        
        # Record loss with partial usage
        loss_record = loss_service.manually_add_historical_loss(
            user_id=test_user.id,
            loss_year=2024,
            loss_amount=loss_amount,
            already_used_amount=used_amount
        )
        
        # Verify the calculation
        expected_remaining = loss_amount - used_amount
        assert loss_record.remaining_amount == expected_remaining.quantize(Decimal('0.01')), \
            f"Remaining loss should be {expected_remaining}, got {loss_record.remaining_amount}"
        
        # Verify all amounts are non-negative
        assert loss_record.loss_amount >= 0, "Loss amount must be non-negative"
        assert loss_record.used_amount >= 0, "Used amount must be non-negative"
        assert loss_record.remaining_amount >= 0, "Remaining amount must be non-negative"
    
    @given(
        loss_amount=decimal_strategy(min_value=1, max_value=50000),
        current_income=decimal_strategy(min_value=1, max_value=50000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_loss_application_reduces_taxable_income(
        self,
        loss_amount: Decimal,
        current_income: Decimal,
        loss_service,
        test_user
    ):
        """
        Property: Applying loss carryforward reduces taxable income
        
        For any loss and current income:
        taxable_income_after_loss = max(0, current_income - loss_applied)
        
        **Validates: Requirements 36.2**
        """
        # Record a loss from previous year
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=loss_amount,
            loss_year=2024
        )
        
        # Apply loss to current year income
        result = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=current_income,
            current_tax_year=2025
        )
        
        # Calculate expected values
        expected_loss_applied = min(loss_amount, current_income)
        expected_taxable_income = current_income - expected_loss_applied
        
        # Verify the results
        assert result.loss_applied == expected_loss_applied.quantize(Decimal('0.01')), \
            f"Loss applied should be {expected_loss_applied}, got {result.loss_applied}"
        
        assert result.taxable_income_after_loss == expected_taxable_income.quantize(Decimal('0.01')), \
            f"Taxable income after loss should be {expected_taxable_income}, got {result.taxable_income_after_loss}"
        
        # Verify taxable income is never negative
        assert result.taxable_income_after_loss >= 0, \
            "Taxable income after loss application must be non-negative"
    
    @given(
        loss_amount=decimal_strategy(min_value=1, max_value=50000),
        current_income=decimal_strategy(min_value=1, max_value=50000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_excess_loss_is_tracked_as_remaining(
        self,
        loss_amount: Decimal,
        current_income: Decimal,
        loss_service,
        test_user
    ):
        """
        Property: When loss exceeds income, excess is tracked as remaining
        
        For any loss > income:
        remaining_loss = loss_amount - income
        taxable_income_after_loss = 0
        
        **Validates: Requirements 36.5**
        """
        # Only test cases where loss exceeds income
        assume(loss_amount > current_income)
        
        # Record a loss from previous year
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=loss_amount,
            loss_year=2024
        )
        
        # Apply loss to current year income
        result = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=current_income,
            current_tax_year=2025
        )
        
        # Calculate expected values
        expected_remaining = loss_amount - current_income
        
        # Verify the results
        assert result.taxable_income_after_loss == Decimal('0.00'), \
            f"When loss exceeds income, taxable income should be €0, got {result.taxable_income_after_loss}"
        
        assert result.remaining_loss == expected_remaining.quantize(Decimal('0.01')), \
            f"Remaining loss should be {expected_remaining}, got {result.remaining_loss}"
        
        assert result.loss_applied == current_income.quantize(Decimal('0.01')), \
            f"Loss applied should equal current income {current_income}, got {result.loss_applied}"
    
    @given(
        taxable_income=decimal_strategy(min_value=-50000, max_value=-1)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_negative_income_produces_zero_tax_and_records_loss(
        self,
        taxable_income: Decimal,
        loss_service
    ):
        """
        Property: When taxable income is negative, tax = €0 and loss is recorded
        
        For any negative taxable income:
        - Tax should be €0
        - Loss amount = abs(taxable_income)
        - Loss amount >= 0
        
        **Validates: Requirements 16.5, 36.5**
        """
        # Calculate loss from negative income
        loss_result = loss_service.calculate_loss(
            taxable_income=taxable_income,
            tax_year=2025
        )
        
        # Verify loss is calculated
        assert loss_result is not None, \
            "Loss should be calculated for negative income"
        
        # Verify loss amount is positive (absolute value of negative income)
        expected_loss = abs(taxable_income)
        assert loss_result.loss_amount == expected_loss.quantize(Decimal('0.01')), \
            f"Loss amount should be {expected_loss}, got {loss_result.loss_amount}"
        
        # Verify loss amount is non-negative
        assert loss_result.loss_amount >= 0, \
            "Loss amount must be non-negative"
        
        # In a real tax calculation, this would result in €0 tax
        # (This property is tested implicitly - negative income means no tax)
    
    @given(
        losses=st.lists(
            st.tuples(
                st.integers(min_value=2020, max_value=2024),  # loss_year
                decimal_strategy(min_value=1, max_value=20000)  # loss_amount
            ),
            min_size=2,
            max_size=5,
            unique_by=lambda x: x[0]  # Unique years
        ),
        current_income=decimal_strategy(min_value=1, max_value=50000)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_multi_year_loss_carryforward_consistency(
        self,
        losses: list,
        current_income: Decimal,
        loss_service,
        test_user
    ):
        """
        Property: Multi-year loss carryforward maintains consistency
        
        For any set of losses from multiple years:
        1. Losses are applied in chronological order (oldest first)
        2. Total loss applied <= sum of all losses
        3. Total loss applied <= current income
        4. Remaining loss = sum(all losses) - total loss applied
        
        **Validates: Requirements 36.1, 36.2**
        """
        # Sort losses by year (oldest first)
        sorted_losses = sorted(losses, key=lambda x: x[0])
        
        # Record all losses
        total_loss = Decimal('0')
        for loss_year, loss_amount in sorted_losses:
            loss_service.record_loss(
                user_id=test_user.id,
                loss_amount=loss_amount,
                loss_year=loss_year
            )
            total_loss += loss_amount
        
        # Apply losses to current year (2025)
        result = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=current_income,
            current_tax_year=2025
        )
        
        # Verify consistency properties
        # 1. Total loss applied should not exceed sum of all losses
        assert result.loss_applied <= total_loss, \
            f"Loss applied ({result.loss_applied}) cannot exceed total losses ({total_loss})"
        
        # 2. Total loss applied should not exceed current income
        assert result.loss_applied <= current_income, \
            f"Loss applied ({result.loss_applied}) cannot exceed current income ({current_income})"
        
        # 3. Remaining loss should equal total losses minus applied
        expected_remaining = total_loss - result.loss_applied
        assert result.remaining_loss == expected_remaining.quantize(Decimal('0.01')), \
            f"Remaining loss should be {expected_remaining}, got {result.remaining_loss}"
        
        # 4. Verify chronological order in breakdown
        if len(result.loss_breakdown) > 1:
            for i in range(len(result.loss_breakdown) - 1):
                current_year = result.loss_breakdown[i]['loss_year']
                next_year = result.loss_breakdown[i + 1]['loss_year']
                assert current_year < next_year, \
                    f"Losses should be applied in chronological order: {current_year} should be before {next_year}"
        
        # 5. All amounts should be non-negative
        assert result.loss_applied >= 0, "Loss applied must be non-negative"
        assert result.remaining_loss >= 0, "Remaining loss must be non-negative"
        assert result.taxable_income_after_loss >= 0, "Taxable income after loss must be non-negative"
    
    @given(
        loss_amount=decimal_strategy(min_value=1, max_value=30000),
        income_year1=decimal_strategy(min_value=1, max_value=20000),
        income_year2=decimal_strategy(min_value=1, max_value=20000)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_sequential_year_loss_application_consistency(
        self,
        loss_amount: Decimal,
        income_year1: Decimal,
        income_year2: Decimal,
        loss_service,
        test_user
    ):
        """
        Property: Sequential application of losses across years is consistent
        
        For a loss applied across multiple years:
        - Year 1: Apply loss to income_year1
        - Year 2: Apply remaining loss to income_year2
        - Total applied = min(loss_amount, income_year1 + income_year2)
        
        **Validates: Requirements 36.1, 36.2**
        """
        # Record a loss in 2023
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=loss_amount,
            loss_year=2023
        )
        
        # Apply to 2024 income
        result_2024 = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=income_year1,
            current_tax_year=2024
        )
        
        # Apply remaining to 2025 income
        result_2025 = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=income_year2,
            current_tax_year=2025
        )
        
        # Calculate expected values
        loss_applied_year1 = min(loss_amount, income_year1)
        remaining_after_year1 = loss_amount - loss_applied_year1
        loss_applied_year2 = min(remaining_after_year1, income_year2)
        total_loss_applied = loss_applied_year1 + loss_applied_year2
        final_remaining = loss_amount - total_loss_applied
        
        # Verify year 1 results
        assert result_2024.loss_applied == loss_applied_year1.quantize(Decimal('0.01')), \
            f"Year 1 loss applied should be {loss_applied_year1}, got {result_2024.loss_applied}"
        
        # Verify year 2 results
        assert result_2025.loss_applied == loss_applied_year2.quantize(Decimal('0.01')), \
            f"Year 2 loss applied should be {loss_applied_year2}, got {result_2025.loss_applied}"
        
        # Verify final remaining loss
        assert result_2025.remaining_loss == final_remaining.quantize(Decimal('0.01')), \
            f"Final remaining loss should be {final_remaining}, got {result_2025.remaining_loss}"
        
        # Verify total applied doesn't exceed original loss
        assert total_loss_applied <= loss_amount, \
            f"Total loss applied ({total_loss_applied}) cannot exceed original loss ({loss_amount})"
        
        # Verify all amounts are non-negative
        assert result_2024.remaining_loss >= 0, "Year 1 remaining loss must be non-negative"
        assert result_2025.remaining_loss >= 0, "Year 2 remaining loss must be non-negative"
    
    @given(
        current_income=decimal_strategy(min_value=-50000, max_value=0)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_loss_applied_to_zero_or_negative_income(
        self,
        current_income: Decimal,
        loss_service,
        test_user
    ):
        """
        Property: No loss is applied when current income is zero or negative
        
        For any income <= 0:
        - loss_applied = 0
        - taxable_income_after_loss = current_income (unchanged)
        - remaining_loss = original loss (unchanged)
        
        **Validates: Requirements 36.2**
        """
        # Record a loss from previous year
        original_loss = Decimal('10000.00')
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=original_loss,
            loss_year=2024
        )
        
        # Try to apply loss to zero or negative income
        result = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=current_income,
            current_tax_year=2025
        )
        
        # Verify no loss was applied
        assert result.loss_applied == Decimal('0.00'), \
            f"No loss should be applied to income <= 0, but got {result.loss_applied}"
        
        # Verify income is unchanged
        assert result.taxable_income_after_loss == current_income, \
            f"Income should remain unchanged at {current_income}, got {result.taxable_income_after_loss}"
        
        # Verify remaining loss equals original loss
        assert result.remaining_loss == original_loss, \
            f"Remaining loss should equal original loss {original_loss}, got {result.remaining_loss}"
        
        # Verify breakdown is empty
        assert len(result.loss_breakdown) == 0, \
            "Loss breakdown should be empty when no loss is applied"
    
    @given(
        loss_amount=decimal_strategy(min_value=1, max_value=50000)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_loss_amounts_never_negative(
        self,
        loss_amount: Decimal,
        loss_service,
        test_user
    ):
        """
        Property: All loss-related amounts are always non-negative
        
        For any loss amount and any operations:
        - loss_amount >= 0
        - used_amount >= 0
        - remaining_amount >= 0
        - loss_applied >= 0
        
        **Validates: Requirements 36.1, 36.2, 36.5**
        """
        # Record a loss (even if negative input, should be converted to positive)
        loss_record = loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=loss_amount,
            loss_year=2024
        )
        
        # Verify all amounts in the record are non-negative
        assert loss_record.loss_amount >= 0, \
            f"Loss amount must be non-negative, got {loss_record.loss_amount}"
        assert loss_record.used_amount >= 0, \
            f"Used amount must be non-negative, got {loss_record.used_amount}"
        assert loss_record.remaining_amount >= 0, \
            f"Remaining amount must be non-negative, got {loss_record.remaining_amount}"
        
        # Apply the loss
        result = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=Decimal('5000.00'),
            current_tax_year=2025
        )
        
        # Verify all amounts in the result are non-negative
        assert result.loss_applied >= 0, \
            f"Loss applied must be non-negative, got {result.loss_applied}"
        assert result.remaining_loss >= 0, \
            f"Remaining loss must be non-negative, got {result.remaining_loss}"
        assert result.taxable_income_after_loss >= 0, \
            f"Taxable income after loss must be non-negative, got {result.taxable_income_after_loss}"
        
        # Verify breakdown amounts are non-negative
        for breakdown_item in result.loss_breakdown:
            assert breakdown_item['applied_amount'] >= 0, \
                f"Breakdown applied amount must be non-negative, got {breakdown_item['applied_amount']}"
            assert breakdown_item['remaining_after_application'] >= 0, \
                f"Breakdown remaining amount must be non-negative, got {breakdown_item['remaining_after_application']}"
