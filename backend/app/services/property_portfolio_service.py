"""
Property Portfolio Service

Provides portfolio-level analysis and bulk operations for multiple properties.

Features:
- Portfolio comparison across properties
- Rental yield and expense ratio calculations
- Bulk operations (depreciation, archive, transaction linking)
"""

from decimal import Decimal
from datetime import date
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
from sqlalchemy.orm import Session

from app.models.property import Property, PropertyStatus
from app.models.transaction import Transaction
from app.services.property_service import PropertyService
from app.services.annual_depreciation_service import AnnualDepreciationService


logger = logging.getLogger(__name__)


class PropertyPortfolioService:
    """
    Service for portfolio-level property analysis and bulk operations.
    """
    
    def __init__(self, db: Session):
        """
        Initialize portfolio service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.property_service = PropertyService(db)
        self.annual_depreciation_service = AnnualDepreciationService(db)
    
    def compare_portfolio_properties(
        self,
        user_id: int,
        year: Optional[int] = None,
        sort_by: str = "net_income",
        sort_order: str = "desc"
    ) -> List[Dict[str, Any]]:
        """
        Compare performance across all user properties.
        
        Calculates and compares:
        - Rental income
        - Total expenses
        - Net income
        - Rental yield (net income / purchase price * 100)
        - Expense ratio (expenses / rental income * 100)
        - Depreciation amount
        
        Identifies:
        - Best performing property (highest net income)
        - Worst performing property (lowest net income)
        - Highest rental yield
        - Lowest expense ratio
        
        Args:
            user_id: ID of the user
            year: Optional year filter (default: current year)
            sort_by: Field to sort by (net_income, rental_yield, expense_ratio, rental_income)
            sort_order: Sort order (asc, desc)
            
        Returns:
            List of property comparison dictionaries with performance metrics
        """
        if year is None:
            year = date.today().year
        
        # Get all active real estate properties for user (exclude devices, vehicles, etc.)
        properties = self.db.query(Property).filter(
            Property.user_id == user_id,
            Property.status == PropertyStatus.ACTIVE,
            Property.asset_type == "real_estate",
        ).all()
        
        if not properties:
            logger.info(f"No active properties found for user {user_id}")
            return []
        
        comparisons = []
        
        for property in properties:
            # Calculate metrics for this property
            metrics = self.property_service.calculate_property_metrics(
                property.id, user_id, year
            )
            
            # Calculate rental yield (net income / purchase price * 100)
            # Skip placeholder properties (purchase_price <= 0.01) to avoid absurd percentages
            rental_yield = Decimal("0")
            if property.purchase_price > Decimal("0.01"):
                rental_yield = (
                    metrics.net_rental_income / property.purchase_price * Decimal("100")
                )
            
            # Calculate expense ratio (expenses / rental income * 100)
            expense_ratio = Decimal("0")
            if metrics.total_rental_income > 0:
                expense_ratio = (
                    metrics.total_expenses / metrics.total_rental_income * Decimal("100")
                )
            
            comparison = {
                "property_id": str(property.id),
                "address": property.address,
                "property_type": property.property_type.value,
                "purchase_price": float(property.purchase_price),
                "rental_income": float(metrics.total_rental_income),
                "expenses": float(metrics.total_expenses),
                "net_income": float(metrics.net_rental_income),
                "rental_yield": float(rental_yield),
                "expense_ratio": float(expense_ratio),
                "depreciation": float(metrics.annual_depreciation),
                "accumulated_depreciation": float(metrics.accumulated_depreciation)
            }
            
            comparisons.append(comparison)
        
        # Sort comparisons
        reverse = (sort_order == "desc")
        
        sort_key_map = {
            "rental_yield": lambda x: x["rental_yield"],
            "expense_ratio": lambda x: x["expense_ratio"],
            "rental_income": lambda x: x["rental_income"],
            "net_income": lambda x: x["net_income"]
        }
        
        sort_key = sort_key_map.get(sort_by, sort_key_map["net_income"])
        comparisons.sort(key=sort_key, reverse=reverse)
        
        # Log portfolio comparison
        logger.info(
            "Portfolio comparison generated",
            extra={
                "user_id": user_id,
                "year": year,
                "property_count": len(comparisons),
                "sort_by": sort_by,
                "sort_order": sort_order,
                "total_rental_income": sum(c["rental_income"] for c in comparisons),
                "total_net_income": sum(c["net_income"] for c in comparisons)
            }
        )
        
        return comparisons
    
    def get_portfolio_summary(
        self,
        user_id: int,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get portfolio-level summary statistics.
        
        Args:
            user_id: ID of the user
            year: Optional year filter (default: current year)
            
        Returns:
            Dictionary with portfolio summary
        """
        comparisons = self.compare_portfolio_properties(user_id, year)
        
        if not comparisons:
            return {
                "year": year or date.today().year,
                "property_count": 0,
                "total_rental_income": 0.0,
                "total_expenses": 0.0,
                "total_net_income": 0.0,
                "average_rental_yield": 0.0,
                "average_expense_ratio": 0.0,
                "best_performer": None,
                "worst_performer": None
            }
        
        total_rental_income = sum(c["rental_income"] for c in comparisons)
        total_expenses = sum(c["expenses"] for c in comparisons)
        total_net_income = sum(c["net_income"] for c in comparisons)
        
        # Calculate averages
        avg_rental_yield = sum(c["rental_yield"] for c in comparisons) / len(comparisons)
        avg_expense_ratio = sum(c["expense_ratio"] for c in comparisons) / len(comparisons)
        
        # Find best and worst performers
        best_performer = max(comparisons, key=lambda x: x["net_income"])
        worst_performer = min(comparisons, key=lambda x: x["net_income"])
        
        return {
            "year": year or date.today().year,
            "property_count": len(comparisons),
            "total_rental_income": total_rental_income,
            "total_expenses": total_expenses,
            "total_net_income": total_net_income,
            "average_rental_yield": avg_rental_yield,
            "average_expense_ratio": avg_expense_ratio,
            "best_performer": {
                "property_id": best_performer["property_id"],
                "address": best_performer["address"],
                "net_income": best_performer["net_income"]
            },
            "worst_performer": {
                "property_id": worst_performer["property_id"],
                "address": worst_performer["address"],
                "net_income": worst_performer["net_income"]
            }
        }
    
    def bulk_generate_annual_depreciation(
        self,
        user_id: int,
        property_ids: List[UUID],
        year: int
    ) -> Dict[str, Any]:
        """
        Generate annual depreciation for multiple properties.
        
        Args:
            user_id: ID of the user
            property_ids: List of property UUIDs
            year: Tax year to generate depreciation for
            
        Returns:
            Dictionary with generation summary
        """
        results = {
            "year": year,
            "requested_properties": len(property_ids),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "transactions_created": [],
            "errors": []
        }
        
        for property_id in property_ids:
            try:
                # Validate ownership
                self.property_service._validate_ownership(property_id, user_id)
                
                # Generate depreciation for single property
                # Note: We need to filter by property_id in the service
                result = self.annual_depreciation_service.generate_annual_depreciation(
                    year, user_id=user_id
                )
                
                if result.transactions_created > 0:
                    results["successful"] += 1
                    results["transactions_created"].extend([str(t.id) for t in result.transactions])
                else:
                    results["skipped"] += 1
                    
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "property_id": str(property_id),
                    "error": str(e)
                })
                logger.error(
                    f"Bulk depreciation generation failed for property {property_id}: {e}",
                    exc_info=True
                )
        
        logger.info(
            "Bulk depreciation generation completed",
            extra={
                "user_id": user_id,
                "year": year,
                "requested": results["requested_properties"],
                "successful": results["successful"],
                "failed": results["failed"],
                "skipped": results["skipped"]
            }
        )
        
        return results
    
    def bulk_archive_properties(
        self,
        user_id: int,
        property_ids: List[UUID]
    ) -> Dict[str, Any]:
        """
        Archive multiple properties.
        
        Args:
            user_id: ID of the user
            property_ids: List of property UUIDs to archive
            
        Returns:
            Dictionary with archive summary
        """
        results = {
            "requested_properties": len(property_ids),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        for property_id in property_ids:
            try:
                # Archive property (validates ownership internally)
                self.property_service.archive_property(property_id, user_id)
                results["successful"] += 1
                
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "property_id": str(property_id),
                    "error": str(e)
                })
                logger.error(
                    f"Bulk archive failed for property {property_id}: {e}",
                    exc_info=True
                )
        
        logger.info(
            "Bulk archive completed",
            extra={
                "user_id": user_id,
                "requested": results["requested_properties"],
                "successful": results["successful"],
                "failed": results["failed"]
            }
        )
        
        return results
    
    def bulk_link_transactions(
        self,
        user_id: int,
        property_id: UUID,
        transaction_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Link multiple transactions to a property.
        
        Args:
            user_id: ID of the user
            property_id: UUID of the property
            transaction_ids: List of transaction IDs to link
            
        Returns:
            Dictionary with linking summary
        """
        results = {
            "property_id": str(property_id),
            "requested_transactions": len(transaction_ids),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        for transaction_id in transaction_ids:
            try:
                # Link transaction (validates ownership internally)
                self.property_service.link_transaction_to_property(
                    transaction_id, property_id, user_id
                )
                results["successful"] += 1
                
            except Exception as e:
                self.db.rollback()
                results["failed"] += 1
                results["errors"].append({
                    "transaction_id": transaction_id,
                    "error": str(e)
                })
                logger.error(
                    f"Bulk link failed for transaction {transaction_id}: {e}",
                    exc_info=True
                )
        
        logger.info(
            "Bulk transaction linking completed",
            extra={
                "user_id": user_id,
                "property_id": str(property_id),
                "requested": results["requested_transactions"],
                "successful": results["successful"],
                "failed": results["failed"]
            }
        )
        
        return results
