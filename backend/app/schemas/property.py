"""Property schemas for request/response validation"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, computed_field
from app.models.property import PropertyType, PropertyStatus


class PropertyBase(BaseModel):
    """Base property schema with common fields"""
    property_type: PropertyType = Field(
        default=PropertyType.RENTAL,
        description="Property type: rental, owner_occupied, or mixed_use"
    )
    rental_percentage: Decimal = Field(
        default=Decimal("100.00"),
        ge=0,
        le=100,
        description="Percentage used for rental (0-100, relevant for mixed_use)"
    )
    street: str = Field(..., min_length=1, max_length=255, description="Street address")
    city: str = Field(..., min_length=1, max_length=100, description="City")
    postal_code: str = Field(..., min_length=1, max_length=10, description="Postal code")
    purchase_date: date = Field(..., description="Property purchase date")
    purchase_price: Decimal = Field(
        ...,
        gt=0,
        le=100_000_000,
        description="Total purchase price (must be > 0 and <= 100,000,000 EUR)"
    )
    building_value: Optional[Decimal] = Field(
        None,
        gt=0,
        description="Depreciable building value (if not provided, calculated as 80% of purchase_price)"
    )
    construction_year: Optional[int] = Field(
        None,
        ge=1800,
        description="Year of construction (affects depreciation rate)"
    )
    depreciation_rate: Optional[Decimal] = Field(
        None,
        ge=Decimal("0.001"),
        le=Decimal("0.10"),
        description="Annual depreciation rate (0.1% to 10%, auto-determined if not provided)"
    )
    grunderwerbsteuer: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Property transfer tax paid"
    )
    notary_fees: Optional[Decimal] = Field(None, ge=0, description="Notary fees paid")
    registry_fees: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Land registry fees (Eintragungsgebühr)"
    )

    @field_validator('purchase_date')
    @classmethod
    def validate_purchase_date(cls, v: date) -> date:
        """Validate purchase date is not in the future"""
        if v > date.today():
            raise ValueError(
                f"Purchase date cannot be in the future. "
                f"Provided date: {v.strftime('%Y-%m-%d')}, "
                f"Today: {date.today().strftime('%Y-%m-%d')}"
            )
        return v

    @field_validator('construction_year')
    @classmethod
    def validate_construction_year(cls, v: Optional[int]) -> Optional[int]:
        """Validate construction year is not in the future"""
        if v is not None:
            current_year = date.today().year
            if v > current_year:
                raise ValueError(
                    f"Construction year cannot be in the future. "
                    f"Provided year: {v}, Current year: {current_year}"
                )
        return v

    @field_validator('purchase_price')
    @classmethod
    def validate_purchase_price(cls, v: Decimal) -> Decimal:
        """Validate purchase price and ensure 2 decimal places"""
        if v <= 0:
            raise ValueError(
                f"Purchase price must be greater than 0. Provided: €{v}"
            )
        if v > 100_000_000:
            raise ValueError(
                f"Purchase price must be <= €100,000,000. Provided: €{v}"
            )
        return v.quantize(Decimal('0.01'))

    @field_validator('building_value')
    @classmethod
    def validate_building_value(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate building value if provided"""
        if v is not None:
            if v <= 0:
                raise ValueError(
                    f"Building value must be greater than 0. Provided: €{v}"
                )
            return v.quantize(Decimal('0.01'))
        return v

    @field_validator('depreciation_rate')
    @classmethod
    def validate_depreciation_rate(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate depreciation rate is within acceptable range"""
        if v is not None:
            if v < Decimal("0.001"):
                raise ValueError(
                    f"Depreciation rate must be >= 0.1% (0.001). Provided: {v}"
                )
            if v > Decimal("0.10"):
                raise ValueError(
                    f"Depreciation rate must be <= 10% (0.10). Provided: {v}"
                )
            return v.quantize(Decimal('0.0001'))
        return v

    @field_validator('rental_percentage')
    @classmethod
    def validate_rental_percentage(cls, v: Decimal) -> Decimal:
        """Validate rental percentage is between 0 and 100"""
        if v < 0 or v > 100:
            raise ValueError(
                f"Rental percentage must be between 0 and 100. Provided: {v}"
            )
        return v.quantize(Decimal('0.01'))

    @field_validator('street', 'city', 'postal_code')
    @classmethod
    def validate_address_fields(cls, v: str) -> str:
        """Validate address fields are not empty"""
        v = v.strip()
        if len(v) == 0:
            raise ValueError(
                "Address fields cannot be empty. Please provide a valid value."
            )
        return v


class PropertyCreate(PropertyBase):
    """Property creation schema with comprehensive validation"""
    monthly_rent: Optional[Decimal] = Field(
        None,
        gt=0,
        le=100_000,
        description="Monthly rental income (if set, auto-creates recurring rental income transaction)"
    )
    rent_start_date: Optional[date] = Field(
        None,
        description="Start date for rental income (defaults to purchase_date)"
    )

    @model_validator(mode='after')
    def validate_building_value_vs_purchase_price(self):
        """Validate building_value <= purchase_price after model initialization"""
        # Auto-calculate building_value as 80% if not provided
        if self.building_value is None:
            self.building_value = (self.purchase_price * Decimal("0.80")).quantize(
                Decimal('0.01')
            )
        
        # Validate building_value <= purchase_price
        if self.building_value > self.purchase_price:
            raise ValueError(
                f"Building value (€{self.building_value}) cannot exceed "
                f"purchase price (€{self.purchase_price})"
            )
        
        return self

    @model_validator(mode='after')
    def auto_determine_depreciation_rate(self):
        """Auto-determine depreciation rate based on construction year if not provided"""
        if self.depreciation_rate is None:
            # Austrian tax law: buildings before 1915 = 1.5%, 1915+ = 2.0%
            if self.construction_year and self.construction_year < 1915:
                self.depreciation_rate = Decimal("0.015")
            else:
                self.depreciation_rate = Decimal("0.020")
        
        return self

    @model_validator(mode='after')
    def validate_rental_percentage_for_type(self):
        """Validate rental_percentage is appropriate for property_type"""
        if self.property_type == PropertyType.RENTAL and self.rental_percentage != 100:
            raise ValueError(
                f"Rental properties must have rental_percentage = 100. "
                f"Provided: {self.rental_percentage}. "
                f"Use property_type='mixed_use' for partial rental."
            )
        
        if self.property_type == PropertyType.OWNER_OCCUPIED and self.rental_percentage != 0:
            raise ValueError(
                f"Owner-occupied properties must have rental_percentage = 0. "
                f"Provided: {self.rental_percentage}. "
                f"Use property_type='mixed_use' for partial rental."
            )
        
        if self.property_type == PropertyType.MIXED_USE:
            if self.rental_percentage <= 0 or self.rental_percentage >= 100:
                raise ValueError(
                    f"Mixed-use properties must have rental_percentage between 0 and 100 (exclusive). "
                    f"Provided: {self.rental_percentage}"
                )
        
        return self


class PropertyUpdate(BaseModel):
    """Property update schema (all fields optional except immutable fields)"""
    property_type: Optional[PropertyType] = None
    rental_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    street: Optional[str] = Field(None, min_length=1, max_length=255)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    postal_code: Optional[str] = Field(None, min_length=1, max_length=10)
    # purchase_date and purchase_price are editable (OCR may extract incorrect values)
    purchase_date: Optional[date] = None
    purchase_price: Optional[Decimal] = Field(None, gt=0)
    building_value: Optional[Decimal] = Field(None, gt=0)
    construction_year: Optional[int] = Field(None, ge=1800)
    depreciation_rate: Optional[Decimal] = Field(
        None,
        ge=Decimal("0.001"),
        le=Decimal("0.10")
    )
    grunderwerbsteuer: Optional[Decimal] = Field(None, ge=0)
    notary_fees: Optional[Decimal] = Field(None, ge=0)
    registry_fees: Optional[Decimal] = Field(None, ge=0)
    status: Optional[PropertyStatus] = None
    sale_date: Optional[date] = None

    @field_validator('construction_year')
    @classmethod
    def validate_construction_year(cls, v: Optional[int]) -> Optional[int]:
        """Validate construction year is not in the future"""
        if v is not None:
            current_year = date.today().year
            if v > current_year:
                raise ValueError(
                    f"Construction year cannot be in the future. "
                    f"Provided year: {v}, Current year: {current_year}"
                )
        return v

    @field_validator('building_value')
    @classmethod
    def validate_building_value(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate building value if provided"""
        if v is not None:
            if v <= 0:
                raise ValueError(
                    f"Building value must be greater than 0. Provided: €{v}"
                )
            return v.quantize(Decimal('0.01'))
        return v

    @field_validator('depreciation_rate')
    @classmethod
    def validate_depreciation_rate(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate depreciation rate is within acceptable range"""
        if v is not None:
            if v < Decimal("0.001"):
                raise ValueError(
                    f"Depreciation rate must be >= 0.1% (0.001). Provided: {v}"
                )
            if v > Decimal("0.10"):
                raise ValueError(
                    f"Depreciation rate must be <= 10% (0.10). Provided: {v}"
                )
            return v.quantize(Decimal('0.0001'))
        return v

    @field_validator('rental_percentage')
    @classmethod
    def validate_rental_percentage(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate rental percentage is between 0 and 100"""
        if v is not None:
            if v < 0 or v > 100:
                raise ValueError(
                    f"Rental percentage must be between 0 and 100. Provided: {v}"
                )
            return v.quantize(Decimal('0.01'))
        return v

    @field_validator('street', 'city', 'postal_code')
    @classmethod
    def validate_address_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate address fields are not empty if provided"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                raise ValueError(
                    "Address fields cannot be empty. Please provide a valid value."
                )
        return v

    @model_validator(mode='after')
    def validate_sale_date_with_status(self):
        """Validate sale_date is provided when status is 'sold'"""
        if self.status == PropertyStatus.SOLD and self.sale_date is None:
            raise ValueError(
                "sale_date is required when status is 'sold'"
            )
        return self


class PropertyResponse(BaseModel):
    """Property response schema for API responses"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: int
    property_type: PropertyType
    rental_percentage: Decimal
    address: str
    street: str
    city: str
    postal_code: str
    purchase_date: date
    purchase_price: Decimal
    building_value: Decimal
    land_value: Optional[Decimal]
    grunderwerbsteuer: Optional[Decimal]
    notary_fees: Optional[Decimal]
    registry_fees: Optional[Decimal]
    construction_year: Optional[int]
    depreciation_rate: Decimal
    status: PropertyStatus
    sale_date: Optional[date]
    kaufvertrag_document_id: Optional[int]
    mietvertrag_document_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class PropertyListItem(BaseModel):
    """Simplified property schema for list views"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    property_type: PropertyType
    street: str
    city: str
    postal_code: str
    purchase_date: date
    building_value: Decimal
    depreciation_rate: Decimal
    status: PropertyStatus
    created_at: datetime
    
    @computed_field
    @property
    def address(self) -> str:
        """Computed address field from components"""
        return f"{self.street}, {self.postal_code} {self.city}"


class PropertyMetrics(BaseModel):
    """Property financial metrics"""
    property_id: UUID
    accumulated_depreciation: Decimal = Field(
        description="Total depreciation claimed to date"
    )
    remaining_depreciable_value: Decimal = Field(
        description="Building value minus accumulated depreciation"
    )
    annual_depreciation: Decimal = Field(
        description="Current year depreciation amount"
    )
    total_rental_income: Decimal = Field(
        default=Decimal("0"),
        description="Total rental income for the period"
    )
    total_expenses: Decimal = Field(
        default=Decimal("0"),
        description="Total property expenses for the period"
    )
    net_rental_income: Decimal = Field(
        default=Decimal("0"),
        description="Rental income minus expenses"
    )
    years_remaining: Optional[Decimal] = Field(
        None,
        description="Estimated years until fully depreciated"
    )
    warnings: list = Field(
        default_factory=list,
        description="Tax validation warnings (e.g., no rental income)"
    )


class PropertyListResponse(BaseModel):
    """Property list response with optional metrics"""
    total: int
    properties: list[PropertyListItem]
    include_archived: bool = False


class PropertyWithMetrics(BaseModel):
    """Property with embedded metrics for optimized list views"""
    model_config = ConfigDict(from_attributes=True)
    
    # Property fields
    id: UUID
    property_type: PropertyType
    address: str
    purchase_date: date
    building_value: Decimal
    depreciation_rate: Decimal
    status: PropertyStatus
    created_at: datetime
    
    # Embedded metrics
    metrics: PropertyMetrics


class PropertyListWithMetricsResponse(BaseModel):
    """Property list response with embedded metrics and pagination"""
    total: int = Field(description="Total number of properties (for pagination)")
    skip: int = Field(description="Number of records skipped")
    limit: int = Field(description="Maximum number of records returned")
    properties: list[PropertyWithMetrics] = Field(description="List of properties with metrics")
    include_archived: bool = False


class PropertyDetailResponse(PropertyResponse):
    """Detailed property response with metrics"""
    metrics: Optional[PropertyMetrics] = None


class HistoricalDepreciationYear(BaseModel):
    """Historical depreciation year data for preview"""
    year: int = Field(description="Tax year")
    amount: Decimal = Field(description="Depreciation amount for this year")
    transaction_date: date = Field(description="Transaction date (December 31 of year)")


class HistoricalDepreciationPreview(BaseModel):
    """Preview of historical depreciation backfill"""
    property_id: UUID
    years: list[HistoricalDepreciationYear] = Field(
        description="List of years with depreciation amounts"
    )
    total_amount: Decimal = Field(
        description="Total depreciation amount across all years"
    )
    years_count: int = Field(
        description="Number of years to backfill"
    )


class BackfillDepreciationResult(BaseModel):
    """Result of historical depreciation backfill"""
    property_id: UUID
    years_backfilled: int = Field(
        description="Number of years backfilled"
    )
    total_amount: Decimal = Field(
        description="Total depreciation amount created"
    )
    transaction_ids: list[int] = Field(
        description="IDs of created transactions"
    )


class AnnualDepreciationResponse(BaseModel):
    """Response for annual depreciation generation"""
    year: int = Field(description="Tax year for which depreciation was generated")
    properties_processed: int = Field(
        description="Total number of properties processed"
    )
    transactions_created: int = Field(
        description="Number of depreciation transactions created"
    )
    properties_skipped: int = Field(
        description="Number of properties skipped (already exists or fully depreciated)"
    )
    total_amount: Decimal = Field(
        description="Total depreciation amount generated"
    )
    transaction_ids: list[int] = Field(
        description="IDs of created transactions"
    )
    skipped_details: list[dict] = Field(
        default_factory=list,
        description="Details of skipped properties with reasons"
    )
