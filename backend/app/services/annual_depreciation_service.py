"""
Annual Depreciation Service

Generates annual depreciation transactions for all active properties at year-end.

Typically run at year-end (December 31) via Celery scheduled task.
Can also be triggered manually by users or admins.
"""

from decimal import Decimal
from datetime import date
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import extract
import logging

from app.models.property import Property, PropertyStatus
from app.models.transaction import Transaction, TransactionType, ExpenseCategory
from app.services.afa_calculator import AfACalculator
from app.services.error_tracker import ErrorTracker
from app.core.metrics import depreciation_generated_counter


logger = logging.getLogger(__name__)


class AnnualDepreciationResult:
    """Result of annual depreciation generation"""
    
    def __init__(
        self,
        year: int,
        properties_processed: int,
        transactions_created: int,
        properties_skipped: int,
        total_amount: Decimal,
        transactions: List[Transaction],
        skipped_details: List[Dict[str, Any]]
    ):
        self.year = year
        self.properties_processed = properties_processed
        self.transactions_created = transactions_created
        self.properties_skipped = properties_skipped
        self.total_amount = total_amount
        self.transactions = transactions
        self.skipped_details = skipped_details
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "year": self.year,
            "properties_processed": self.properties_processed,
            "transactions_created": self.transactions_created,
            "properties_skipped": self.properties_skipped,
            "total_amount": float(self.total_amount),
            "transaction_ids": [t.id for t in self.transactions],
            "skipped_details": self.skipped_details
        }


class AnnualDepreciationService:
    """
    Generates annual depreciation transactions for all active properties.
    
    This service is typically run at year-end to create depreciation expense
    transactions for all active rental properties.
    """
    
    def __init__(self, db: Session):
        """
        Initialize annual depreciation service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.afa_calculator = AfACalculator(db)
    
    def generate_annual_depreciation(
        self, 
        year: int, 
        user_id: Optional[int] = None
    ) -> AnnualDepreciationResult:
        """
        Generate depreciation transactions for all active properties.
        
        Creates transactions dated December 31 of the specified year.
        Marks transactions as system-generated.
        Prevents duplicate transactions.
        
        Args:
            year: Tax year to generate depreciation for
            user_id: If provided, only generate for this user's properties.
                    If None, generate for all users (admin function).
        
        Returns:
            AnnualDepreciationResult with summary of generated transactions
        """
        # Query active properties
        query = self.db.query(Property).filter(
            Property.status == PropertyStatus.ACTIVE
        )
        
        if user_id:
            query = query.filter(Property.user_id == user_id)
        
        properties = query.all()
        
        created_transactions = []
        skipped_properties = []
        
        for property in properties:
            try:
                # Check if depreciation already exists for this year
                if self._depreciation_exists(property.id, year):
                    skipped_properties.append({
                        "property_id": str(property.id),
                        "address": property.address,
                        "reason": "already_exists"
                    })
                    logger.info(
                        f"Skipping property {property.id} - depreciation already exists for {year}"
                    )
                    continue
                
                # Calculate depreciation
                amount = self.afa_calculator.calculate_annual_depreciation(property, year)
                
                if amount == Decimal("0"):
                    skipped_properties.append({
                        "property_id": str(property.id),
                        "address": property.address,
                        "reason": "fully_depreciated"
                    })
                    logger.info(
                        f"Skipping property {property.id} - fully depreciated or zero amount"
                    )
                    continue
                
                # Create transaction
                transaction = Transaction(
                    user_id=property.user_id,
                    property_id=property.id,
                    type=TransactionType.EXPENSE,
                    amount=amount,
                    transaction_date=date(year, 12, 31),
                    description=f"AfA {property.address} ({year})",
                    expense_category=ExpenseCategory.DEPRECIATION_AFA,
                    is_deductible=True,
                    is_system_generated=True,
                    import_source="annual_depreciation",
                    classification_confidence=Decimal("1.0")
                )
                
                self.db.add(transaction)
                created_transactions.append(transaction)
                
                # Increment Prometheus counter for depreciation generation
                depreciation_generated_counter.labels(
                    user_id=str(property.user_id),
                    year=str(year)
                ).inc()
                
                logger.info(
                    f"Created depreciation transaction for property {property.id}: "
                    f"{amount} EUR for year {year}"
                )
                
            except Exception as e:
                logger.error(
                    f"Error generating depreciation for property {property.id}: {e}",
                    exc_info=True
                )
                
                # Track depreciation failure
                ErrorTracker.track_depreciation_failure(
                    property_id=property.id,
                    year=year,
                    error=e,
                    user_id=property.user_id,
                    property_address=property.address,
                    context={
                        "operation": "generate_annual_depreciation",
                        "building_value": str(property.building_value),
                        "depreciation_rate": str(property.depreciation_rate)
                    }
                )
                
                skipped_properties.append({
                    "property_id": str(property.id),
                    "address": property.address,
                    "reason": f"error: {str(e)}"
                })
        
        # Commit all transactions
        try:
            self.db.commit()
            
            # Refresh to get IDs
            for transaction in created_transactions:
                self.db.refresh(transaction)
            
            # Log summary of annual depreciation generation with structured data
            logger.info(
                "Annual depreciation generation completed",
                extra={
                    "year": year,
                    "user_id": user_id if user_id else "all_users",
                    "properties_processed": len(properties),
                    "transactions_created": len(created_transactions),
                    "properties_skipped": len(skipped_properties),
                    "total_amount": float(sum(t.amount for t in created_transactions)),
                    "skip_reasons": {
                        "already_exists": sum(1 for p in skipped_properties if p["reason"] == "already_exists"),
                        "fully_depreciated": sum(1 for p in skipped_properties if p["reason"] == "fully_depreciated"),
                        "errors": sum(1 for p in skipped_properties if "error" in p["reason"])
                    }
                }
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to commit depreciation transactions: {e}", exc_info=True)
            raise RuntimeError(f"Failed to generate annual depreciation: {str(e)}") from e
        
        return AnnualDepreciationResult(
            year=year,
            properties_processed=len(properties),
            transactions_created=len(created_transactions),
            properties_skipped=len(skipped_properties),
            total_amount=sum(t.amount for t in created_transactions),
            transactions=created_transactions,
            skipped_details=skipped_properties
        )
    
    def _depreciation_exists(self, property_id: UUID, year: int) -> bool:
        """
        Check if depreciation already exists for property and year.
        
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
