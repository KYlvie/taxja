"""Loss carryforward service for managing multi-year loss tracking"""
from decimal import Decimal
from typing import List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.loss_carryforward import LossCarryforward


@dataclass
class LossCarryforwardResult:
    """Result of loss carryforward calculation"""
    loss_applied: Decimal
    remaining_loss: Decimal
    taxable_income_after_loss: Decimal
    loss_breakdown: List[dict]


@dataclass
class LossCalculationResult:
    """Result of loss calculation for negative income"""
    loss_amount: Decimal
    tax_year: int
    note: str


class LossCarryforwardService:
    """
    Service for managing loss carryforward (Verlustvortrag).
    
    Handles:
    1. Calculating negative income as loss
    2. Applying previous year losses to current taxable income
    3. Tracking remaining loss amounts
    """
    
    def __init__(self, db: Session):
        """
        Initialize service with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def calculate_loss(
        self,
        taxable_income: Decimal,
        tax_year: int
    ) -> Optional[LossCalculationResult]:
        """
        Calculate loss when taxable income is negative.
        
        Args:
            taxable_income: The taxable income (can be negative)
            tax_year: The tax year for the loss
            
        Returns:
            LossCalculationResult if income is negative, None otherwise
        """
        if not isinstance(taxable_income, Decimal):
            taxable_income = Decimal(str(taxable_income))
        
        # Only calculate loss if income is negative
        if taxable_income >= 0:
            return None
        
        # Loss is the absolute value of negative income
        loss_amount = abs(taxable_income)
        
        return LossCalculationResult(
            loss_amount=loss_amount.quantize(Decimal('0.01')),
            tax_year=tax_year,
            note=f"Loss of €{loss_amount:.2f} recorded for year {tax_year}"
        )
    
    def apply_loss_carryforward(
        self,
        user_id: int,
        current_taxable_income: Decimal,
        current_tax_year: int
    ) -> LossCarryforwardResult:
        """
        Apply previous year losses to current taxable income.
        
        This method:
        1. Retrieves all available losses from previous years
        2. Applies them in chronological order (oldest first)
        3. Updates the used amounts in the database
        4. Returns the adjusted taxable income
        
        Args:
            user_id: The user ID
            current_taxable_income: Current year's taxable income before loss application
            current_tax_year: The current tax year
            
        Returns:
            LossCarryforwardResult with applied losses and adjusted income
        """
        from app.models.loss_carryforward import LossCarryforward
        
        if not isinstance(current_taxable_income, Decimal):
            current_taxable_income = Decimal(str(current_taxable_income))
        
        # If current income is zero or negative, no loss can be applied
        if current_taxable_income <= 0:
            return LossCarryforwardResult(
                loss_applied=Decimal('0.00'),
                remaining_loss=self._get_total_remaining_loss(user_id),
                taxable_income_after_loss=current_taxable_income,
                loss_breakdown=[]
            )
        
        # Get all available losses from previous years (ordered by year, oldest first)
        available_losses = self.db.query(LossCarryforward).filter(
            LossCarryforward.user_id == user_id,
            LossCarryforward.loss_year < current_tax_year,
            LossCarryforward.remaining_amount > 0
        ).order_by(LossCarryforward.loss_year).all()
        
        # Apply losses
        total_loss_applied = Decimal('0.00')
        remaining_taxable_income = current_taxable_income
        loss_breakdown = []
        
        for loss_record in available_losses:
            if remaining_taxable_income <= 0:
                break
            
            # Calculate how much of this loss can be applied
            loss_to_apply = min(
                loss_record.remaining_amount,
                remaining_taxable_income
            )
            
            # Update the loss record
            loss_record.used_amount += loss_to_apply
            loss_record.remaining_amount -= loss_to_apply
            
            # Track the application
            total_loss_applied += loss_to_apply
            remaining_taxable_income -= loss_to_apply
            
            # Add to breakdown
            loss_breakdown.append({
                'loss_year': loss_record.loss_year,
                'original_loss': loss_record.loss_amount,
                'applied_amount': loss_to_apply.quantize(Decimal('0.01')),
                'remaining_after_application': loss_record.remaining_amount.quantize(Decimal('0.01'))
            })
        
        # Commit changes to database
        self.db.commit()
        
        # Calculate total remaining loss across all years
        total_remaining_loss = self._get_total_remaining_loss(user_id)
        
        return LossCarryforwardResult(
            loss_applied=total_loss_applied.quantize(Decimal('0.01')),
            remaining_loss=total_remaining_loss,
            taxable_income_after_loss=remaining_taxable_income.quantize(Decimal('0.01')),
            loss_breakdown=loss_breakdown
        )
    
    def record_loss(
        self,
        user_id: int,
        loss_amount: Decimal,
        loss_year: int
    ) -> 'LossCarryforward':
        """
        Record a new loss for a tax year.
        
        Args:
            user_id: The user ID
            loss_amount: The loss amount (positive value)
            loss_year: The year the loss occurred
            
        Returns:
            The created LossCarryforward record
        """
        from app.models.loss_carryforward import LossCarryforward
        
        if not isinstance(loss_amount, Decimal):
            loss_amount = Decimal(str(loss_amount))
        
        # Ensure loss amount is positive
        loss_amount = abs(loss_amount)
        
        # Check if a loss record already exists for this user and year
        existing_loss = self.db.query(LossCarryforward).filter(
            LossCarryforward.user_id == user_id,
            LossCarryforward.loss_year == loss_year
        ).first()
        
        if existing_loss:
            # Update existing record
            existing_loss.loss_amount = loss_amount
            existing_loss.remaining_amount = loss_amount - existing_loss.used_amount
            self.db.commit()
            return existing_loss
        
        # Create new loss record
        loss_record = LossCarryforward(
            user_id=user_id,
            loss_year=loss_year,
            loss_amount=loss_amount,
            used_amount=Decimal('0.00'),
            remaining_amount=loss_amount
        )
        
        self.db.add(loss_record)
        self.db.commit()
        self.db.refresh(loss_record)
        
        return loss_record
    
    def get_loss_summary(
        self,
        user_id: int,
        current_tax_year: Optional[int] = None
    ) -> dict:
        """
        Get a summary of all losses for a user.
        
        Args:
            user_id: The user ID
            current_tax_year: Optional current tax year to filter losses before this year
            
        Returns:
            Dictionary with loss summary information
        """
        from app.models.loss_carryforward import LossCarryforward
        
        query = self.db.query(LossCarryforward).filter(
            LossCarryforward.user_id == user_id
        )
        
        if current_tax_year:
            query = query.filter(LossCarryforward.loss_year < current_tax_year)
        
        losses = query.order_by(LossCarryforward.loss_year).all()
        
        total_loss = sum(loss.loss_amount for loss in losses)
        total_used = sum(loss.used_amount for loss in losses)
        total_remaining = sum(loss.remaining_amount for loss in losses)
        
        loss_details = [
            {
                'year': loss.loss_year,
                'original_amount': loss.loss_amount,
                'used_amount': loss.used_amount,
                'remaining_amount': loss.remaining_amount
            }
            for loss in losses
        ]
        
        return {
            'total_loss': total_loss,
            'total_used': total_used,
            'total_remaining': total_remaining,
            'loss_details': loss_details
        }
    
    def manually_add_historical_loss(
        self,
        user_id: int,
        loss_year: int,
        loss_amount: Decimal,
        already_used_amount: Decimal = Decimal('0.00')
    ) -> 'LossCarryforward':
        """
        Manually add a historical loss (for legacy data migration).
        
        Args:
            user_id: The user ID
            loss_year: The year the loss occurred
            loss_amount: The original loss amount
            already_used_amount: Amount already used in previous years (default 0)
            
        Returns:
            The created LossCarryforward record
        """
        from app.models.loss_carryforward import LossCarryforward
        
        if not isinstance(loss_amount, Decimal):
            loss_amount = Decimal(str(loss_amount))
        if not isinstance(already_used_amount, Decimal):
            already_used_amount = Decimal(str(already_used_amount))
        
        # Ensure amounts are positive
        loss_amount = abs(loss_amount)
        already_used_amount = abs(already_used_amount)
        
        # Validate that used amount doesn't exceed loss amount
        if already_used_amount > loss_amount:
            raise ValueError("Used amount cannot exceed loss amount")
        
        remaining_amount = loss_amount - already_used_amount
        
        # Check if record already exists
        existing_loss = self.db.query(LossCarryforward).filter(
            LossCarryforward.user_id == user_id,
            LossCarryforward.loss_year == loss_year
        ).first()
        
        if existing_loss:
            # Update existing record
            existing_loss.loss_amount = loss_amount
            existing_loss.used_amount = already_used_amount
            existing_loss.remaining_amount = remaining_amount
            self.db.commit()
            return existing_loss
        
        # Create new record
        loss_record = LossCarryforward(
            user_id=user_id,
            loss_year=loss_year,
            loss_amount=loss_amount,
            used_amount=already_used_amount,
            remaining_amount=remaining_amount
        )
        
        self.db.add(loss_record)
        self.db.commit()
        self.db.refresh(loss_record)
        
        return loss_record
    
    def _get_total_remaining_loss(self, user_id: int) -> Decimal:
        """
        Get total remaining loss across all years for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Total remaining loss amount
        """
        from app.models.loss_carryforward import LossCarryforward
        
        losses = self.db.query(LossCarryforward).filter(
            LossCarryforward.user_id == user_id,
            LossCarryforward.remaining_amount > 0
        ).all()
        
        total = sum(loss.remaining_amount for loss in losses)
        return Decimal(str(total)).quantize(Decimal('0.01'))
