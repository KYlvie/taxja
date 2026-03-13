"""
Property Report Generation Service

Generates property-specific reports including:
- Income statement (rental income and expenses)
- Depreciation schedule (AfA over time)

Supports PDF and CSV export formats.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models.property import Property, PropertyStatus
from app.models.transaction import Transaction, TransactionType, ExpenseCategory, IncomeCategory
from app.services.afa_calculator import AfACalculator
from app.services.property_report_export_service import PropertyReportExportService


class PropertyReportService:
    """Service for generating property-specific financial reports"""

    def __init__(self, db: Session):
        self.db = db
        self.afa_calculator = AfACalculator(db)
        self._redis_client: Optional[redis.Redis] = None
        self._init_redis()
        self.export_service = PropertyReportExportService(language="de")
    
    def _init_redis(self):
        """Initialize synchronous Redis client for caching"""
        try:
            from app.core.config import settings
            import redis
            
            self._redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            # Test connection
            self._redis_client.ping()
        except Exception as e:
            print(f"Redis connection failed: {e}. Caching disabled.")
            self._redis_client = None
    
    def _get_cached_depreciation_schedule(self, property_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached depreciation schedule from Redis.
        
        Args:
            property_id: UUID of the property
            
        Returns:
            Dict with depreciation schedule if cached, None otherwise
        """
        if not self._redis_client:
            return None
        
        try:
            import json
            cache_key = f"depreciation_schedule:{property_id}"
            cached_data = self._redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            print(f"Cache get error for depreciation schedule {property_id}: {e}")
            return None
    
    def _set_cached_depreciation_schedule(self, property_id: str, schedule: Dict[str, Any]) -> bool:
        """
        Set cached depreciation schedule in Redis with 24 hour TTL.
        
        Args:
            property_id: UUID of the property
            schedule: Dict with depreciation schedule to cache
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self._redis_client:
            return False
        
        try:
            import json
            cache_key = f"depreciation_schedule:{property_id}"
            # Cache for 24 hours (86400 seconds)
            self._redis_client.setex(cache_key, 86400, json.dumps(schedule))
            return True
        except Exception as e:
            print(f"Cache set error for depreciation schedule {property_id}: {e}")
            return False

    def generate_income_statement(
        self,
        property_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Generate income statement for a property showing rental income,
        expenses by category, and net income.

        Args:
            property_id: UUID of the property (as string)
            start_date: Start date for report (default: beginning of current year)
            end_date: End date for report (default: today)

        Returns:
            Dictionary with income statement data
        """
        from uuid import UUID
        
        # Convert string to UUID if needed
        if isinstance(property_id, str):
            property_id = UUID(property_id)
        
        # Get property
        property = self.db.query(Property).filter(Property.id == property_id).first()
        if not property:
            raise ValueError(f"Property {property_id} not found")

        # Default date range to current year
        if not start_date:
            start_date = date(date.today().year, 1, 1)
        if not end_date:
            end_date = date.today()

        # Get rental income
        rental_income = (
            self.db.query(func.sum(Transaction.amount))
            .filter(
                Transaction.property_id == property_id,
                Transaction.type == TransactionType.INCOME,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
            )
            .scalar()
            or Decimal("0")
        )

        # Get expenses by category
        expenses_query = (
            self.db.query(
                Transaction.expense_category,
                func.sum(Transaction.amount).label("total"),
            )
            .filter(
                Transaction.property_id == property_id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
            )
            .group_by(Transaction.expense_category)
        )

        expenses_by_category = {}
        total_expenses = Decimal("0")

        for category, amount in expenses_query:
            if category:  # Only include if category is not None
                expenses_by_category[category.value] = float(amount)
                total_expenses += amount

        net_income = rental_income - total_expenses

        return {
            "property": {
                "id": str(property.id),
                "address": property.address,
                "purchase_date": property.purchase_date.isoformat(),
                "building_value": float(property.building_value),
            },
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "income": {
                "rental_income": float(rental_income),
                "total_income": float(rental_income),
            },
            "expenses": {
                "by_category": expenses_by_category,
                "total_expenses": float(total_expenses),
            },
            "net_income": float(net_income),
        }

    def generate_depreciation_schedule(
            self, property_id: str, include_future: bool = True, future_years: int = 10
        ) -> Dict[str, Any]:
            """
            Generate depreciation schedule showing annual depreciation,
            accumulated depreciation, and remaining value by year.

            Includes both historical (actual) and future (projected) depreciation.

            Args:
                property_id: UUID of the property (as string)
                include_future: Whether to include future depreciation projections (default: True)
                future_years: Number of future years to project (default: 10)

            Returns:
                Dictionary with depreciation schedule data including:
                - Historical depreciation (purchase year to current year)
                - Future depreciation projections (if include_future=True)
                - Summary statistics
            """
            from uuid import UUID
            
            # Convert string to UUID if needed
            if isinstance(property_id, str):
                property_id_uuid = UUID(property_id)
            else:
                property_id_uuid = property_id
            
            # Try to get from cache
            cache_key_suffix = f"_{include_future}_{future_years}" if include_future else ""
            cached_schedule = self._get_cached_depreciation_schedule(str(property_id) + cache_key_suffix)
            if cached_schedule:
                return cached_schedule

            # Get property
            property = self.db.query(Property).filter(Property.id == property_id_uuid).first()
            if not property:
                raise ValueError(f"Property {property_id} not found")

            purchase_year = property.purchase_date.year
            current_year = date.today().year

            # Calculate sale year if property is sold
            end_year = property.sale_date.year if property.sale_date else current_year

            # Historical schedule (purchase year to current/sale year)
            historical_schedule = []
            accumulated = Decimal("0")

            for year in range(purchase_year, end_year + 1):
                # Calculate annual depreciation for this year
                annual_depreciation = self.afa_calculator.calculate_annual_depreciation(
                    property, year
                )

                accumulated += annual_depreciation
                remaining = property.building_value - accumulated

                historical_schedule.append({
                    "year": year,
                    "annual_depreciation": float(annual_depreciation),
                    "accumulated_depreciation": float(accumulated),
                    "remaining_value": float(remaining),
                    "is_projected": False
                })

            # Future projections (only if property is active and not fully depreciated)
            future_schedule = []
            if include_future and property.status == PropertyStatus.ACTIVE and accumulated < property.building_value:
                projection_accumulated = accumulated
                projection_year = end_year + 1
                years_projected = 0

                # Project until fully depreciated or future_years limit reached
                while years_projected < future_years and projection_accumulated < property.building_value:
                    # Calculate projected annual depreciation
                    annual_depreciation = self.afa_calculator.calculate_annual_depreciation(
                        property, projection_year
                    )

                    if annual_depreciation == Decimal("0"):
                        # Fully depreciated
                        break

                    projection_accumulated += annual_depreciation
                    remaining = property.building_value - projection_accumulated

                    future_schedule.append({
                        "year": projection_year,
                        "annual_depreciation": float(annual_depreciation),
                        "accumulated_depreciation": float(projection_accumulated),
                        "remaining_value": float(max(remaining, Decimal("0"))),
                        "is_projected": True
                    })

                    projection_year += 1
                    years_projected += 1

            # Combine historical and future schedules
            full_schedule = historical_schedule + future_schedule

            # Calculate years remaining until fully depreciated
            years_remaining = None
            if property.status == PropertyStatus.ACTIVE and accumulated < property.building_value:
                # Calculate based on current depreciation rate
                remaining_value = property.building_value - accumulated
                annual_rate = property.building_value * property.depreciation_rate
                if annual_rate > 0:
                    years_remaining = float((remaining_value / annual_rate).quantize(Decimal("0.1")))

            result = {
                "property": {
                    "id": str(property.id),
                    "address": property.address,
                    "purchase_date": property.purchase_date.isoformat(),
                    "building_value": float(property.building_value),
                    "depreciation_rate": float(property.depreciation_rate),
                    "status": property.status.value,
                    "sale_date": property.sale_date.isoformat() if property.sale_date else None
                },
                "schedule": full_schedule,
                "summary": {
                    "total_years": len(full_schedule),
                    "years_elapsed": len(historical_schedule),
                    "years_projected": len(future_schedule),
                    "total_depreciation": float(property.building_value),
                    "accumulated_depreciation": float(accumulated),
                    "remaining_value": float(property.building_value - accumulated),
                    "years_remaining": years_remaining,
                    "fully_depreciated_year": full_schedule[-1]["year"] if future_schedule and full_schedule[-1]["remaining_value"] == 0 else None
                },
            }

            # Cache the result
            self._set_cached_depreciation_schedule(str(property_id) + cache_key_suffix, result)

            return result


    def export_income_statement_pdf(
        self,
        property_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        language: str = "de",
    ) -> bytes:
        """
        Export income statement to PDF format.

        Args:
            property_id: UUID of the property
            start_date: Start date for report
            end_date: End date for report
            language: Language code (de, en)

        Returns:
            PDF file as bytes
        """
        report_data = self.generate_income_statement(
            property_id, start_date, end_date
        )
        export_service = PropertyReportExportService(language=language)
        return export_service.export_income_statement_pdf(report_data)

    def export_income_statement_csv(
        self,
        property_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        language: str = "de",
    ) -> str:
        """
        Export income statement to CSV format.

        Args:
            property_id: UUID of the property
            start_date: Start date for report
            end_date: End date for report
            language: Language code (de, en)

        Returns:
            CSV content as string
        """
        report_data = self.generate_income_statement(
            property_id, start_date, end_date
        )
        export_service = PropertyReportExportService(language=language)
        return export_service.export_income_statement_csv(report_data)

    def export_depreciation_schedule_pdf(
        self,
        property_id: str,
        include_future: bool = True,
        future_years: int = 10,
        language: str = "de",
    ) -> bytes:
        """
        Export depreciation schedule to PDF format.

        Args:
            property_id: UUID of the property
            include_future: Whether to include future projections
            future_years: Number of future years to project
            language: Language code (de, en)

        Returns:
            PDF file as bytes
        """
        report_data = self.generate_depreciation_schedule(
            property_id, include_future, future_years
        )
        export_service = PropertyReportExportService(language=language)
        return export_service.export_depreciation_schedule_pdf(report_data)

    def export_depreciation_schedule_csv(
        self,
        property_id: str,
        include_future: bool = True,
        future_years: int = 10,
        language: str = "de",
    ) -> str:
        """
        Export depreciation schedule to CSV format.

        Args:
            property_id: UUID of the property
            include_future: Whether to include future projections
            future_years: Number of future years to project
            language: Language code (de, en)

        Returns:
            CSV content as string
        """
        report_data = self.generate_depreciation_schedule(
            property_id, include_future, future_years
        )
        export_service = PropertyReportExportService(language=language)
        return export_service.export_depreciation_schedule_csv(report_data)
