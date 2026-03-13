"""Unit tests for loss carryforward service"""
import pytest
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


class TestLossCalculation:
    """Tests for loss calculation from negative income"""
    
    def test_calculate_loss_with_negative_income(self, loss_service):
        """Test loss calculation when income is negative"""
        taxable_income = Decimal('-5000.00')
        tax_year = 2025
        
        result = loss_service.calculate_loss(taxable_income, tax_year)
        
        assert result is not None
        assert isinstance(result, LossCalculationResult)
        assert result.loss_amount == Decimal('5000.00')
        assert result.tax_year == 2025
        assert '5000.00' in result.note
    
    def test_calculate_loss_with_positive_income(self, loss_service):
        """Test that no loss is calculated for positive income"""
        taxable_income = Decimal('5000.00')
        tax_year = 2025
        
        result = loss_service.calculate_loss(taxable_income, tax_year)
        
        assert result is None
    
    def test_calculate_loss_with_zero_income(self, loss_service):
        """Test that no loss is calculated for zero income"""
        taxable_income = Decimal('0.00')
        tax_year = 2025
        
        result = loss_service.calculate_loss(taxable_income, tax_year)
        
        assert result is None
    
    def test_calculate_loss_with_large_negative_income(self, loss_service):
        """Test loss calculation with large negative amount"""
        taxable_income = Decimal('-50000.50')
        tax_year = 2025
        
        result = loss_service.calculate_loss(taxable_income, tax_year)
        
        assert result is not None
        assert result.loss_amount == Decimal('50000.50')


class TestRecordLoss:
    """Tests for recording losses"""
    
    def test_record_new_loss(self, loss_service, test_user):
        """Test recording a new loss"""
        loss_amount = Decimal('10000.00')
        loss_year = 2024
        
        loss_record = loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=loss_amount,
            loss_year=loss_year
        )
        
        assert loss_record.user_id == test_user.id
        assert loss_record.loss_year == 2024
        assert loss_record.loss_amount == Decimal('10000.00')
        assert loss_record.used_amount == Decimal('0.00')
        assert loss_record.remaining_amount == Decimal('10000.00')
    
    def test_record_loss_updates_existing(self, loss_service, test_user):
        """Test that recording a loss for existing year updates the record"""
        # Record initial loss
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=Decimal('5000.00'),
            loss_year=2024
        )
        
        # Record new loss for same year
        updated_record = loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=Decimal('8000.00'),
            loss_year=2024
        )
        
        assert updated_record.loss_amount == Decimal('8000.00')
        assert updated_record.remaining_amount == Decimal('8000.00')
    
    def test_record_loss_with_negative_amount(self, loss_service, test_user):
        """Test that negative loss amounts are converted to positive"""
        loss_record = loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=Decimal('-3000.00'),
            loss_year=2024
        )
        
        assert loss_record.loss_amount == Decimal('3000.00')


class TestApplyLossCarryforward:
    """Tests for applying loss carryforward to current income"""
    
    def test_apply_single_loss_fully(self, loss_service, test_user):
        """Test applying a single loss that is fully used"""
        # Record a loss from 2024
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=Decimal('5000.00'),
            loss_year=2024
        )
        
        # Apply to 2025 income
        result = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=Decimal('10000.00'),
            current_tax_year=2025
        )
        
        assert result.loss_applied == Decimal('5000.00')
        assert result.taxable_income_after_loss == Decimal('5000.00')
        assert result.remaining_loss == Decimal('0.00')
        assert len(result.loss_breakdown) == 1
        assert result.loss_breakdown[0]['loss_year'] == 2024
        assert result.loss_breakdown[0]['applied_amount'] == Decimal('5000.00')
    
    def test_apply_single_loss_partially(self, loss_service, test_user):
        """Test applying a loss that is only partially used"""
        # Record a loss from 2024
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=Decimal('10000.00'),
            loss_year=2024
        )
        
        # Apply to smaller 2025 income
        result = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=Decimal('6000.00'),
            current_tax_year=2025
        )
        
        assert result.loss_applied == Decimal('6000.00')
        assert result.taxable_income_after_loss == Decimal('0.00')
        assert result.remaining_loss == Decimal('4000.00')
        assert len(result.loss_breakdown) == 1
        assert result.loss_breakdown[0]['remaining_after_application'] == Decimal('4000.00')
    
    def test_apply_multiple_losses_chronologically(self, loss_service, test_user):
        """Test that multiple losses are applied in chronological order (oldest first)"""
        # Record losses from multiple years
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=Decimal('3000.00'),
            loss_year=2023
        )
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=Decimal('4000.00'),
            loss_year=2024
        )
        
        # Apply to 2025 income
        result = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=Decimal('5000.00'),
            current_tax_year=2025
        )
        
        # Should apply 2023 loss first (3000), then part of 2024 loss (2000)
        assert result.loss_applied == Decimal('5000.00')
        assert result.taxable_income_after_loss == Decimal('0.00')
        assert result.remaining_loss == Decimal('2000.00')
        assert len(result.loss_breakdown) == 2
        assert result.loss_breakdown[0]['loss_year'] == 2023
        assert result.loss_breakdown[0]['applied_amount'] == Decimal('3000.00')
        assert result.loss_breakdown[1]['loss_year'] == 2024
        assert result.loss_breakdown[1]['applied_amount'] == Decimal('2000.00')
    
    def test_apply_loss_with_zero_income(self, loss_service, test_user):
        """Test that no loss is applied when current income is zero"""
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=Decimal('5000.00'),
            loss_year=2024
        )
        
        result = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=Decimal('0.00'),
            current_tax_year=2025
        )
        
        assert result.loss_applied == Decimal('0.00')
        assert result.taxable_income_after_loss == Decimal('0.00')
        assert result.remaining_loss == Decimal('5000.00')
        assert len(result.loss_breakdown) == 0
    
    def test_apply_loss_with_negative_income(self, loss_service, test_user):
        """Test that no loss is applied when current income is negative"""
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=Decimal('5000.00'),
            loss_year=2024
        )
        
        result = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=Decimal('-2000.00'),
            current_tax_year=2025
        )
        
        assert result.loss_applied == Decimal('0.00')
        assert result.taxable_income_after_loss == Decimal('-2000.00')
        assert result.remaining_loss == Decimal('5000.00')
    
    def test_apply_loss_only_from_previous_years(self, loss_service, test_user):
        """Test that losses from current or future years are not applied"""
        # Record losses from different years
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=Decimal('3000.00'),
            loss_year=2024
        )
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=Decimal('2000.00'),
            loss_year=2025  # Same year
        )
        loss_service.record_loss(
            user_id=test_user.id,
            loss_amount=Decimal('1000.00'),
            loss_year=2026  # Future year
        )
        
        # Apply to 2025 income
        result = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=Decimal('10000.00'),
            current_tax_year=2025
        )
        
        # Only 2024 loss should be applied
        assert result.loss_applied == Decimal('3000.00')
        assert len(result.loss_breakdown) == 1
        assert result.loss_breakdown[0]['loss_year'] == 2024


class TestManualHistoricalLoss:
    """Tests for manually adding historical losses"""
    
    def test_add_historical_loss_with_no_usage(self, loss_service, test_user):
        """Test adding a historical loss with no prior usage"""
        loss_record = loss_service.manually_add_historical_loss(
            user_id=test_user.id,
            loss_year=2020,
            loss_amount=Decimal('15000.00'),
            already_used_amount=Decimal('0.00')
        )
        
        assert loss_record.loss_year == 2020
        assert loss_record.loss_amount == Decimal('15000.00')
        assert loss_record.used_amount == Decimal('0.00')
        assert loss_record.remaining_amount == Decimal('15000.00')
    
    def test_add_historical_loss_with_partial_usage(self, loss_service, test_user):
        """Test adding a historical loss with partial prior usage"""
        loss_record = loss_service.manually_add_historical_loss(
            user_id=test_user.id,
            loss_year=2020,
            loss_amount=Decimal('20000.00'),
            already_used_amount=Decimal('8000.00')
        )
        
        assert loss_record.loss_amount == Decimal('20000.00')
        assert loss_record.used_amount == Decimal('8000.00')
        assert loss_record.remaining_amount == Decimal('12000.00')
    
    def test_add_historical_loss_with_full_usage(self, loss_service, test_user):
        """Test adding a historical loss that was fully used"""
        loss_record = loss_service.manually_add_historical_loss(
            user_id=test_user.id,
            loss_year=2020,
            loss_amount=Decimal('10000.00'),
            already_used_amount=Decimal('10000.00')
        )
        
        assert loss_record.remaining_amount == Decimal('0.00')
    
    def test_add_historical_loss_invalid_usage(self, loss_service, test_user):
        """Test that adding historical loss with usage > amount raises error"""
        with pytest.raises(ValueError, match="Used amount cannot exceed loss amount"):
            loss_service.manually_add_historical_loss(
                user_id=test_user.id,
                loss_year=2020,
                loss_amount=Decimal('10000.00'),
                already_used_amount=Decimal('15000.00')
            )


class TestLossSummary:
    """Tests for loss summary functionality"""
    
    def test_get_loss_summary_with_multiple_years(self, loss_service, test_user):
        """Test getting loss summary with losses from multiple years"""
        # Add losses
        loss_service.record_loss(test_user.id, Decimal('5000.00'), 2023)
        loss_service.record_loss(test_user.id, Decimal('8000.00'), 2024)
        
        # Apply some losses
        loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=Decimal('6000.00'),
            current_tax_year=2025
        )
        
        # Get summary
        summary = loss_service.get_loss_summary(test_user.id)
        
        assert summary['total_loss'] == Decimal('13000.00')
        assert summary['total_used'] == Decimal('6000.00')
        assert summary['total_remaining'] == Decimal('7000.00')
        assert len(summary['loss_details']) == 2
    
    def test_get_loss_summary_filtered_by_year(self, loss_service, test_user):
        """Test getting loss summary filtered by current tax year"""
        # Add losses
        loss_service.record_loss(test_user.id, Decimal('3000.00'), 2023)
        loss_service.record_loss(test_user.id, Decimal('4000.00'), 2024)
        loss_service.record_loss(test_user.id, Decimal('2000.00'), 2025)
        
        # Get summary for 2025 (should only include 2023 and 2024)
        summary = loss_service.get_loss_summary(test_user.id, current_tax_year=2025)
        
        assert summary['total_loss'] == Decimal('7000.00')
        assert len(summary['loss_details']) == 2
    
    def test_get_loss_summary_empty(self, loss_service, test_user):
        """Test getting loss summary when no losses exist"""
        summary = loss_service.get_loss_summary(test_user.id)
        
        assert summary['total_loss'] == 0
        assert summary['total_used'] == 0
        assert summary['total_remaining'] == 0
        assert len(summary['loss_details']) == 0


class TestLossCarryforwardIntegration:
    """Integration tests for complete loss carryforward scenarios"""
    
    def test_multi_year_loss_carryforward_scenario(self, loss_service, test_user):
        """Test a realistic multi-year loss carryforward scenario"""
        # Year 2023: Loss of €10,000
        loss_service.record_loss(test_user.id, Decimal('10000.00'), 2023)
        
        # Year 2024: Loss of €5,000
        loss_service.record_loss(test_user.id, Decimal('5000.00'), 2024)
        
        # Year 2025: Profit of €8,000 (should use 2023 loss first)
        result_2025 = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=Decimal('8000.00'),
            current_tax_year=2025
        )
        
        assert result_2025.loss_applied == Decimal('8000.00')
        assert result_2025.taxable_income_after_loss == Decimal('0.00')
        assert result_2025.remaining_loss == Decimal('7000.00')  # 2000 from 2023 + 5000 from 2024
        
        # Year 2026: Profit of €10,000 (should use remaining 2023 loss, then 2024 loss)
        result_2026 = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=Decimal('10000.00'),
            current_tax_year=2026
        )
        
        assert result_2026.loss_applied == Decimal('7000.00')
        assert result_2026.taxable_income_after_loss == Decimal('3000.00')
        assert result_2026.remaining_loss == Decimal('0.00')
    
    def test_loss_carryforward_with_subsequent_loss(self, loss_service, test_user):
        """Test loss carryforward when a subsequent year also has a loss"""
        # Year 2023: Loss of €5,000
        loss_service.record_loss(test_user.id, Decimal('5000.00'), 2023)
        
        # Year 2024: Profit of €3,000 (partially uses 2023 loss)
        result_2024 = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=Decimal('3000.00'),
            current_tax_year=2024
        )
        
        assert result_2024.remaining_loss == Decimal('2000.00')
        
        # Year 2025: Loss of €4,000 (new loss, doesn't affect 2023 carryforward)
        loss_service.record_loss(test_user.id, Decimal('4000.00'), 2025)
        
        # Year 2026: Profit of €10,000 (should use remaining 2023 loss, then 2025 loss)
        result_2026 = loss_service.apply_loss_carryforward(
            user_id=test_user.id,
            current_taxable_income=Decimal('10000.00'),
            current_tax_year=2026
        )
        
        assert result_2026.loss_applied == Decimal('6000.00')  # 2000 from 2023 + 4000 from 2025
        assert result_2026.taxable_income_after_loss == Decimal('4000.00')
        assert result_2026.remaining_loss == Decimal('0.00')
