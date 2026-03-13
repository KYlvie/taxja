"""
AfA (Absetzung für Abnutzung) Calculator Service

Calculates depreciation for rental properties according to Austrian tax law.

Austrian Tax Law Rules:
- Buildings constructed before 1915: 1.5% annual depreciation
- Buildings constructed 1915 or later: 2.0% annual depreciation
- Only building value is depreciable (not land)
- Pro-rated for partial year ownership
- Stops when accumulated depreciation reaches building value
- Mixed-use properties: only rental percentage is depreciable
"""

from decimal import Decimal
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.models.property import Property, PropertyType
from app.models.transaction import Transaction, ExpenseCategory, IncomeCategory
from app.services.property_error_integration import track_depreciation_errors
import logging

logger = logging.getLogger(__name__)


class AfACalculator:
    """
    Calculates depreciation (Absetzung für Abnutzung) for rental properties.
    
    All calculations use Decimal for precision and round to 2 decimal places.
    """
    
    def __init__(self, db: Optional[Session] = None):
        """
        Initialize AfA calculator.
        
        Args:
            db: SQLAlchemy database session (required for accumulated depreciation queries)
        """
        self.db = db
        self.warnings = []  # Store warnings for tax report
    
    def determine_depreciation_rate(self, construction_year: Optional[int]) -> Decimal:
        """
        Determine depreciation rate based on construction year per Austrian tax law.
        
        Args:
            construction_year: Year the building was constructed
            
        Returns:
            Decimal("0.015") for pre-1915 buildings (1.5%)
            Decimal("0.020") for 1915+ buildings or unknown (2.0%)
        """
        if construction_year and construction_year < 1915:
            return Decimal("0.015")
        return Decimal("0.020")
    
    @track_depreciation_errors
    def calculate_annual_depreciation(
        self, 
        property: Property, 
        year: int
    ) -> Decimal:
        """
        Calculate annual depreciation for a property in a given year.
        
        Handles:
        - Full year depreciation
        - Pro-rated first year (based on purchase month)
        - Pro-rated last year (if sold mid-year)
        - Building value limit (stops when fully depreciated)
        - Mixed-use properties (only rental percentage)
        - Owner-occupied properties (no depreciation)
        
        Args:
            property: Property model instance
            year: Tax year to calculate depreciation for
            
        Returns:
            Decimal amount rounded to 2 decimal places
        """
        # Owner-occupied properties are not depreciable
        if property.property_type == PropertyType.OWNER_OCCUPIED:
            return Decimal("0")
        
        # Check for rental income (warn if rental property has no income)
        if property.property_type == PropertyType.RENTAL:
            self._check_rental_income_warning(property, year)
        
        # Check if property was owned during this year
        if year < property.purchase_date.year:
            return Decimal("0")
        
        if property.sale_date and year > property.sale_date.year:
            return Decimal("0")
        
        # Get accumulated depreciation up to previous year
        if self.db is None:
            raise ValueError("Database session required for accumulated depreciation calculation")
        
        accumulated = self.get_accumulated_depreciation(property.id, year - 1)
        
        # Calculate depreciable value (considering rental percentage for mixed-use)
        depreciable_value = property.building_value
        if property.property_type == PropertyType.MIXED_USE:
            rental_pct = property.rental_percentage / Decimal("100")
            depreciable_value = depreciable_value * rental_pct
        
        # Check if already fully depreciated
        if accumulated >= depreciable_value:
            return Decimal("0")
        
        # Calculate base annual depreciation
        annual_amount = depreciable_value * property.depreciation_rate
        
        # Pro-rate for partial year
        months_owned = self._calculate_months_owned(property, year)
        if months_owned < 12:
            annual_amount = (annual_amount * months_owned) / 12
        
        # Ensure we don't exceed building value
        remaining = depreciable_value - accumulated
        final_amount = min(annual_amount, remaining)
        
        return final_amount.quantize(Decimal("0.01"))
    
    def calculate_prorated_depreciation(
        self, 
        property: Property,
        months_owned: int
    ) -> Decimal:
        """
        Calculate pro-rated depreciation for partial year ownership.
        
        Args:
            property: Property model instance
            months_owned: Number of months owned in the year (1-12)
            
        Returns:
            Decimal amount rounded to 2 decimal places
        """
        # Owner-occupied properties are not depreciable
        if property.property_type == PropertyType.OWNER_OCCUPIED:
            return Decimal("0")
        
        # Calculate depreciable value (considering rental percentage for mixed-use)
        depreciable_value = property.building_value
        if property.property_type == PropertyType.MIXED_USE:
            rental_pct = property.rental_percentage / Decimal("100")
            depreciable_value = depreciable_value * rental_pct
        
        # Calculate annual depreciation
        annual = depreciable_value * property.depreciation_rate
        
        # Pro-rate for months owned
        prorated = (annual * months_owned) / 12
        
        return prorated.quantize(Decimal("0.01"))
    
    def get_accumulated_depreciation(
        self, 
        property_id, 
        up_to_year: Optional[int] = None
    ) -> Decimal:
        """
        Get total accumulated depreciation for a property.
        
        Sums all depreciation transactions up to specified year.
        
        Args:
            property_id: UUID of the property
            up_to_year: Optional year limit (inclusive). If None, sums all years.
            
        Returns:
            Decimal total accumulated depreciation
        """
        if self.db is None:
            raise ValueError("Database session required for accumulated depreciation calculation")
        
        query = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.property_id == property_id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION
        )
        
        if up_to_year:
            query = query.filter(
                extract('year', Transaction.transaction_date) <= up_to_year
            )
        
        result = query.scalar()
        return result or Decimal("0")
    
    def _calculate_months_owned(self, property: Property, year: int) -> int:
        """
        Calculate number of months property was owned in given year.
        
        Args:
            property: Property model instance
            year: Tax year
            
        Returns:
            Number of months (1-12)
        """
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        
        # Determine ownership period within the year
        ownership_start = max(property.purchase_date, year_start)
        ownership_end = min(property.sale_date or year_end, year_end)
        
        # Calculate months (inclusive)
        months = (ownership_end.year - ownership_start.year) * 12
        months += ownership_end.month - ownership_start.month + 1
        
        return min(months, 12)
    
    def _get_rental_income_for_year(self, property_id, year: int) -> Decimal:
        """
        Get total rental income for a property in a given year.
        
        Args:
            property_id: UUID of the property
            year: Tax year
            
        Returns:
            Decimal total rental income
        """
        if self.db is None:
            return Decimal("0")
        
        result = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.property_id == property_id,
            Transaction.income_category == IncomeCategory.RENTAL,
            extract('year', Transaction.transaction_date) == year
        ).scalar()
        
        return result or Decimal("0")
    
    def _check_rental_income_warning(self, property: Property, year: int) -> None:
        """
        Check if rental property has rental income and add warning if not.
        
        Args:
            property: Property model instance
            year: Tax year
        """
        rental_income = self._get_rental_income_for_year(property.id, year)
        
        if rental_income == 0:
            # Calculate months since purchase
            year_start = date(year, 1, 1)
            ownership_start = max(property.purchase_date, year_start)
            months_since_purchase = (date(year, 12, 31).year - ownership_start.year) * 12
            months_since_purchase += date(year, 12, 31).month - ownership_start.month + 1
            
            # Add appropriate warning based on vacancy duration
            if months_since_purchase <= 6:
                warning_level = "info"
                message_de = (
                    f"Keine Mieteinnahmen für {property.address} im Jahr {year}. "
                    f"Leerstandsphase: {months_since_purchase} Monate. "
                    f"Dokumentieren Sie Ihre Vermietungsbemühungen (Inserate, Besichtigungen)."
                )
                message_en = (
                    f"No rental income for {property.address} in {year}. "
                    f"Vacancy period: {months_since_purchase} months. "
                    f"Document your rental efforts (listings, viewings)."
                )
                message_zh = (
                    f"{property.address} 在 {year} 年无租金收入。"
                    f"空置期：{months_since_purchase} 个月。"
                    f"请记录您的出租努力（广告、看房）。"
                )
            elif months_since_purchase <= 12:
                warning_level = "warning"
                message_de = (
                    f"⚠️ Längere Leerstandsphase für {property.address}: {months_since_purchase} Monate ohne Mieteinnahmen. "
                    f"Das Finanzamt könnte die Vermietungsabsicht anzweifeln. "
                    f"Dokumentieren Sie: Inserate, Besichtigungen, Ablehnungsgründe."
                )
                message_en = (
                    f"⚠️ Extended vacancy for {property.address}: {months_since_purchase} months without rental income. "
                    f"Tax office may question rental intent. "
                    f"Document: Listings, viewings, rejection reasons."
                )
                message_zh = (
                    f"⚠️ {property.address} 长期空置：{months_since_purchase} 个月无租金收入。"
                    f"税务局可能质疑出租意图。"
                    f"请记录：广告、看房、拒绝原因。"
                )
            else:
                warning_level = "error"
                message_de = (
                    f"🚨 ACHTUNG: {property.address} hat seit über 12 Monaten keine Mieteinnahmen! "
                    f"Das Finanzamt wird die Vermietungsabsicht stark anzweifeln. "
                    f"Ihr AfA-Abzug ist gefährdet! "
                    f"Erwägen Sie, die Immobilie als 'Eigengenutzt' umzuklassifizieren."
                )
                message_en = (
                    f"🚨 WARNING: {property.address} has no rental income for over 12 months! "
                    f"Tax office will strongly question rental intent. "
                    f"Your depreciation deduction is at risk! "
                    f"Consider reclassifying the property as 'Owner-Occupied'."
                )
                message_zh = (
                    f"🚨 警告：{property.address} 超过12个月无租金收入！"
                    f"税务局将强烈质疑出租意图。"
                    f"您的折旧抵扣有风险！"
                    f"考虑将房产重新分类为'自住'。"
                )
            
            self.warnings.append({
                "property_id": str(property.id),
                "property_address": property.address,
                "year": year,
                "level": warning_level,
                "type": "NO_RENTAL_INCOME",
                "months_vacant": months_since_purchase,
                "message_de": message_de,
                "message_en": message_en,
                "message_zh": message_zh,
            })
            
            logger.warning(
                f"Property {property.id} ({property.address}) has no rental income in {year}. "
                f"Vacancy: {months_since_purchase} months. Level: {warning_level}"
            )
    
    def get_warnings(self) -> list:
        """
        Get all warnings generated during depreciation calculations.
        
        Returns:
            List of warning dictionaries
        """
        return self.warnings
    
    def clear_warnings(self) -> None:
        """Clear all warnings."""
        self.warnings = []
