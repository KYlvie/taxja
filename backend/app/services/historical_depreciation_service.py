"""
Historical Depreciation Service

Backfills depreciation transactions for properties purchased in previous years.

Use case: New user registers a property bought in 2020, needs depreciation
for 2020, 2021, 2022, 2023, 2024, 2025 to have accurate accumulated depreciation.
"""

from decimal import Decimal
from datetime import date
from typing import List, Optional
from uuid import UUID
import logging
from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.models.property import Property
from app.models.transaction import Transaction, TransactionType, ExpenseCategory
from app.services.afa_calculator import AfACalculator
from app.services.error_tracker import ErrorTracker
from app.services.property_error_integration import track_backfill_errors
from app.core.metrics import backfill_duration_histogram
import time


logger = logging.getLogger(__name__)


class HistoricalDepreciationYear:
    """Data class for historical depreciation year preview"""
    
    def __init__(self, year: int, amount: Decimal, transaction_date: date):
        self.year = year
        self.amount = amount
        self.transaction_date = transaction_date
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "year": self.year,
            "amount": float(self.amount),
            "transaction_date": self.transaction_date.isoformat()
        }


class BackfillResult:
    """Result of backfill operation"""
    
    def __init__(
        self,
        property_id: UUID,
        years_backfilled: int,
        total_amount: Decimal,
        transactions: List[Transaction]
    ):
        self.property_id = property_id
        self.years_backfilled = years_backfilled
        self.total_amount = total_amount
        self.transactions = transactions
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "property_id": str(self.property_id),
            "years_backfilled": self.years_backfilled,
            "total_amount": float(self.total_amount),
            "transaction_ids": [t.id for t in self.transactions]
        }


class HistoricalDepreciationService:
    """
    Backfills depreciation transactions for properties purchased in previous years.
    
    This service ensures that properties registered after their purchase date
    have complete depreciation history for accurate tax calculations.
    """
    
    def __init__(self, db: Session):
        """
        Initialize historical depreciation service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.afa_calculator = AfACalculator(db)
    
    def calculate_historical_depreciation(
        self, 
        property_id: UUID
    ) -> List[HistoricalDepreciationYear]:
        """
        Calculate depreciation for all years from purchase to current year.
        
        Returns list of year/amount/date tuples for preview.
        Does not create transactions.
        
        Args:
            property_id: UUID of the property
            
        Returns:
            List of HistoricalDepreciationYear objects
            
        Raises:
            ValueError: If property not found
        """
        property = self._get_property(property_id)
        current_year = date.today().year
        
        results = []
        for year in range(property.purchase_date.year, current_year + 1):
            # Skip if depreciation already exists for this year
            if self._depreciation_exists(property_id, year):
                continue
            
            # Calculate depreciation for this year
            amount = self.afa_calculator.calculate_annual_depreciation(property, year)
            
            # Only include years with non-zero depreciation
            if amount > 0:
                results.append(HistoricalDepreciationYear(
                    year=year,
                    amount=amount,
                    transaction_date=date(year, 12, 31)
                ))
        
        # Log preview calculation
        logger.info(
            "Historical depreciation preview calculated",
            extra={
                "property_id": str(property_id),
                "property_address": property.address,
                "years_to_backfill": len(results),
                "total_amount": float(sum(r.amount for r in results)) if results else 0.0,
                "year_range": f"{results[0].year}-{results[-1].year}" if results else "none"
            }
        )
        
        return results
    
    @track_backfill_errors
    def backfill_depreciation(
        self, 
        property_id: UUID, 
        user_id: int,
        confirm: bool = False
    ) -> BackfillResult:
        """
        Create historical depreciation transactions.
        
        Creates transactions dated December 31 of each year.
        Marks as system-generated.
        Validates no duplicates.
        
        Args:
            property_id: UUID of the property
            user_id: ID of the user (for ownership validation)
            confirm: If False, returns preview without creating transactions
            
        Returns:
            BackfillResult with summary of created transactions
            
        Raises:
            ValueError: If property not found or does not belong to user
        """
        # Start timing for Prometheus histogram
        start_time = time.time()
        
        try:
            property = self._get_property(property_id)
            
            # Validate ownership - return 404 for both not found and not owned
            if property.user_id != user_id:
                raise ValueError(f"Property with id {property_id} not found")
            
            # Calculate historical depreciation
            historical_years = self.calculate_historical_depreciation(property_id)
            
            # If not confirmed, return preview
            if not confirm:
                total_amount = sum(year_data.amount for year_data in historical_years)
                return BackfillResult(
                    property_id=property_id,
                    years_backfilled=len(historical_years),
                    total_amount=total_amount,
                    transactions=[]
                )
            
            # Create transactions
            created_transactions = []
            
            try:
                for year_data in historical_years:
                    transaction = Transaction(
                        user_id=user_id,
                        property_id=property_id,
                        type=TransactionType.EXPENSE,
                        amount=year_data.amount,
                        transaction_date=year_data.transaction_date,
                        description=f"AfA {property.address} ({year_data.year})",
                        expense_category=ExpenseCategory.DEPRECIATION_AFA,
                        is_deductible=True,
                        is_system_generated=True,
                        import_source="historical_backfill",
                        classification_confidence=Decimal("1.0")
                    )
                    self.db.add(transaction)
                    created_transactions.append(transaction)
                
                # Commit all transactions
                self.db.commit()
                
                # Refresh to get IDs
                for transaction in created_transactions:
                    self.db.refresh(transaction)
                
                # Log backfill operation with structured data
                logger.info(
                    "Historical depreciation backfill completed",
                    extra={
                        "user_id": user_id,
                        "property_id": str(property_id),
                        "property_address": property.address,
                        "years_backfilled": len(created_transactions),
                        "total_amount": float(sum(t.amount for t in created_transactions)),
                        "year_range": f"{historical_years[0].year}-{historical_years[-1].year}" if historical_years else "none",
                        "transaction_ids": [t.id for t in created_transactions]
                    }
                )
                
                return BackfillResult(
                    property_id=property_id,
                    years_backfilled=len(created_transactions),
                    total_amount=sum(t.amount for t in created_transactions),
                    transactions=created_transactions
                )
                
            except Exception as e:
                # Rollback on any error
                self.db.rollback()
                raise RuntimeError(f"Failed to backfill depreciation: {str(e)}") from e
        
        finally:
            # Record duration in Prometheus histogram (only if confirmed)
            if confirm:
                duration = time.time() - start_time
                backfill_duration_histogram.labels(property_id=str(property_id)).observe(duration)
    
    def _get_property(self, property_id: UUID) -> Property:
        """
        Get property by ID.
        
        Args:
            property_id: UUID of the property
            
        Returns:
            Property model instance
            
        Raises:
            ValueError: If property not found
        """
        property = self.db.query(Property).filter(Property.id == property_id).first()
        if not property:
            raise ValueError(f"Property not found: {property_id}")
        return property
    
    def _depreciation_exists(self, property_id: UUID, year: int) -> bool:
        """
        Check if depreciation transaction already exists for property and year.
        
        Args:
            property_id: UUID of the property
            year: Tax year
            
        Returns:
            True if depreciation exists, False otherwise
        """
        exists = self.db.query(Transaction).filter(
            Transaction.property_id == property_id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA,
            extract('year', Transaction.transaction_date) == year
        ).first()
        return exists is not None
