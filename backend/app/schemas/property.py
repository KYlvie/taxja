"""Property schemas for request/response validation"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, computed_field
from app.models.property import PropertyType, PropertyStatus, BuildingUse
from app.schemas.asset_recognition import (
    AssetRecognitionDecision,
    ComparisonBasis,
    DepreciationMethod,
    IfbRateSource,
    UsefulLifeSource,
    VatRecoverableStatus,
)


# Austrian tax law: standard useful life for common asset types
ASSET_USEFUL_LIFE = {
    "vehicle": 8,           # PKW: 8 years
    "electric_vehicle": 8,  # E-Auto: 8 years (eligible for IFB 15%)
    "computer": 3,          # Computer, Laptop, Tablet
    "phone": 3,             # Smartphone
    "office_furniture": 10, # Büromöbel
    "machinery": 10,        # Maschinen
    "tools": 5,             # Werkzeuge
    "software": 3,          # Software-Lizenzen
    "other_equipment": 5,   # Sonstige Betriebsausstattung
    "real_estate": 50,      # Gebäude (handled separately by construction_year)
}

ASSET_ACQUISITION_KINDS = {
    "purchase",
    "lease",
    "finance_lease",
    "self_constructed",
    "used_asset",
}


VALID_DISPOSAL_REASONS = {"sold", "scrapped", "fully_depreciated", "private_withdrawal"}


class DisposalRequest(BaseModel):
    """Request schema for disposing of an asset/property"""
    disposal_reason: str = Field(
        ...,
        description="Reason for disposal: sold, scrapped, fully_depreciated, private_withdrawal"
    )
    disposal_date: date = Field(..., description="Date of disposal")
    sale_price: Optional[Decimal] = Field(
        None,
        gt=0,
        le=Decimal("100000000"),
        description="Sale price (required when disposal_reason is 'sold')"
    )

    @field_validator("disposal_reason")
    @classmethod
    def validate_disposal_reason(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_DISPOSAL_REASONS:
            raise ValueError(
                f"Invalid disposal_reason '{v}'. "
                f"Must be one of: {sorted(VALID_DISPOSAL_REASONS)}"
            )
        return v

    @model_validator(mode="after")
    def validate_sale_price_required_for_sold(self):
        if self.disposal_reason == "sold" and self.sale_price is None:
            raise ValueError("sale_price is required when disposal_reason is 'sold'")
        return self


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
    building_use: BuildingUse = Field(
        default=BuildingUse.RESIDENTIAL,
        description="Building usage: residential (Wohngebäude, 1.5% AfA) or commercial (Betriebsgebäude, 2.5% AfA)"
    )
    eco_standard: bool = Field(
        default=False,
        description="Meets eco/klimaaktiv standard (enables extended 3× AfA for 3 years on 2024-2026 residential builds)"
    )
    depreciation_rate: Optional[Decimal] = Field(
        None,
        ge=Decimal("0.001"),
        le=Decimal("1.00"),
        description="Annual depreciation rate (0.1% to 100%, auto-determined from building_use if not provided)"
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
            if v > Decimal("1.00"):
                raise ValueError(
                    f"Depreciation rate must be <= 100% (1.00). Provided: {v}"
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
        """Auto-determine depreciation rate from building_use if not provided.

        Since 1. StRefG 2015/2016 (§8 Abs 1 / §16 Abs 1 Z 8 EStG):
        - Residential (Wohngebäude): 1.5%
        - Commercial (Betriebsgebäude): 2.5%

        The old pre-1915 vs post-1915 distinction no longer applies.
        Accelerated depreciation (3×/2× for post-2020) is applied dynamically
        in AfACalculator, not stored here.
        """
        if self.depreciation_rate is None:
            if self.building_use == BuildingUse.COMMERCIAL:
                self.depreciation_rate = Decimal("0.025")  # 2.5% Betriebsgebäude
            else:
                self.depreciation_rate = Decimal("0.015")  # 1.5% Wohngebäude

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
    building_use: Optional[BuildingUse] = None
    eco_standard: Optional[bool] = None
    depreciation_rate: Optional[Decimal] = Field(
        None,
        ge=Decimal("0.001"),
        le=Decimal("1.00")
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
            if v > Decimal("1.00"):
                raise ValueError(
                    f"Depreciation rate must be <= 100% (1.00). Provided: {v}"
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
    asset_type: Optional[str] = "real_estate"
    sub_category: Optional[str] = None
    name: Optional[str] = None
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
    building_use: BuildingUse = BuildingUse.RESIDENTIAL
    eco_standard: bool = False
    depreciation_rate: Decimal
    useful_life_years: Optional[int] = None
    acquisition_kind: Optional[str] = None
    put_into_use_date: Optional[date] = None
    is_used_asset: bool = False
    first_registration_date: Optional[date] = None
    prior_owner_usage_years: Optional[Decimal] = None
    business_use_percentage: Optional[Decimal] = Decimal("100.00")
    comparison_basis: Optional[ComparisonBasis] = None
    comparison_amount: Optional[Decimal] = None
    gwg_eligible: bool = False
    gwg_elected: bool = False
    depreciation_method: Optional[DepreciationMethod] = None
    degressive_afa_rate: Optional[Decimal] = None
    useful_life_source: Optional[UsefulLifeSource] = None
    income_tax_cost_cap: Optional[Decimal] = None
    income_tax_depreciable_base: Optional[Decimal] = None
    vat_recoverable_status: Optional[VatRecoverableStatus] = None
    ifb_candidate: bool = False
    ifb_rate: Optional[Decimal] = None
    ifb_rate_source: Optional[IfbRateSource] = None
    recognition_decision: Optional[AssetRecognitionDecision] = None
    policy_confidence: Optional[Decimal] = None
    supplier: Optional[str] = None
    accumulated_depreciation: Optional[Decimal] = Decimal("0")
    status: PropertyStatus
    sale_date: Optional[date]
    disposal_reason: Optional[str] = None
    kaufvertrag_document_id: Optional[int]
    mietvertrag_document_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def annual_depreciation(self) -> Decimal:
        return (self.building_value * self.depreciation_rate).quantize(Decimal("0.01"))

    @computed_field
    @property
    def remaining_value(self) -> Decimal:
        accumulated = self.accumulated_depreciation or Decimal("0")
        return max(self.building_value - accumulated, Decimal("0")).quantize(Decimal("0.01"))


class PropertyListItem(BaseModel):
    """Simplified property schema for list views"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    asset_type: Optional[str] = "real_estate"
    name: Optional[str] = None
    property_type: PropertyType
    street: str
    city: str
    postal_code: str
    purchase_date: date
    purchase_price: Decimal
    building_value: Decimal
    depreciation_rate: Decimal
    rental_percentage: Decimal = Decimal("100.00")
    useful_life_years: Optional[int] = None
    business_use_percentage: Optional[Decimal] = Decimal("100.00")
    accumulated_depreciation: Optional[Decimal] = Decimal("0")
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


# ---------------------------------------------------------------------------
# Asset (non-real-estate) schemas
# ---------------------------------------------------------------------------

class AssetCreate(BaseModel):
    """Schema for creating a non-real-estate asset (vehicle, equipment, etc.)"""
    asset_type: str = Field(
        ...,
        description="Asset type: vehicle, electric_vehicle, computer, phone, "
                    "office_furniture, machinery, tools, software, other_equipment"
    )
    sub_category: Optional[str] = Field(
        None, max_length=100,
        description="Sub-category (e.g., 'PKW', 'Laptop', 'CNC-Maschine')"
    )
    name: str = Field(
        ..., min_length=1, max_length=255,
        description="Asset name/description (e.g., 'VW Golf 2024', 'MacBook Pro 16')"
    )
    purchase_date: date = Field(..., description="Purchase/acquisition date")
    purchase_price: Decimal = Field(
        ..., gt=0, le=Decimal("10000000"),
        description="Purchase price incl. VAT (Anschaffungskosten)"
    )
    supplier: Optional[str] = Field(
        None, max_length=255,
        description="Supplier/dealer name"
    )
    business_use_percentage: Decimal = Field(
        default=Decimal("100.00"), ge=0, le=100,
        description="Percentage used for business (betriebliche Nutzung)"
    )
    useful_life_years: Optional[int] = Field(
        None, ge=1, le=50,
        description="Useful life in years (auto-determined from asset_type if not provided)"
    )
    document_id: Optional[int] = Field(
        None, description="ID of the source document (Kaufvertrag/Rechnung)"
    )
    acquisition_kind: str = Field(
        default="purchase",
        description="Acquisition kind: purchase, lease, finance_lease, self_constructed, used_asset"
    )
    put_into_use_date: Optional[date] = Field(
        None,
        description="Date the asset was first put into business use (Inbetriebnahme)"
    )
    is_used_asset: bool = Field(
        default=False,
        description="Whether the asset was bought used (gebraucht)"
    )
    first_registration_date: Optional[date] = Field(
        None,
        description="Vehicle first registration date, mainly for used PKW useful life handling"
    )
    prior_owner_usage_years: Optional[Decimal] = Field(
        None,
        ge=0,
        le=Decimal("50.00"),
        description="Estimated years used by a previous owner for used vehicles"
    )
    comparison_basis: Optional[ComparisonBasis] = Field(
        None,
        description="Tax comparison basis used for GWG/VAT logic"
    )
    comparison_amount: Optional[Decimal] = Field(
        None,
        gt=0,
        le=Decimal("10000000"),
        description="Tax comparison amount after VAT basis selection"
    )
    gwg_eligible: bool = Field(
        default=False,
        description="Whether the asset is eligible for GWG treatment"
    )
    gwg_elected: bool = Field(
        default=False,
        description="Whether the user elected GWG immediate expensing"
    )
    depreciation_method: Optional[DepreciationMethod] = Field(
        default=DepreciationMethod.LINEAR,
        description="Chosen depreciation method"
    )
    degressive_afa_rate: Optional[Decimal] = Field(
        None,
        gt=0,
        le=Decimal("0.3000"),
        description="Chosen degressive AfA rate when depreciation_method=degressive"
    )
    useful_life_source: Optional[UsefulLifeSource] = Field(
        None,
        description="Where the useful life came from: law, tax practice, system_default, user_override"
    )
    income_tax_cost_cap: Optional[Decimal] = Field(
        None,
        ge=0,
        le=Decimal("10000000"),
        description="Income-tax cost cap, e.g. EUR 40,000 for PKW/Kombi"
    )
    income_tax_depreciable_base: Optional[Decimal] = Field(
        None,
        ge=0,
        le=Decimal("10000000"),
        description="Depreciable basis after applying cost caps or other policy adjustments"
    )
    vat_recoverable_status: Optional[VatRecoverableStatus] = Field(
        None,
        description="Likely VAT recovery status"
    )
    ifb_candidate: bool = Field(
        default=False,
        description="Whether the asset is a candidate for IFB"
    )
    ifb_rate: Optional[Decimal] = Field(
        None,
        ge=0,
        le=Decimal("1.0000"),
        description="IFB rate candidate"
    )
    ifb_rate_source: Optional[IfbRateSource] = Field(
        None,
        description="Source of the IFB rate"
    )
    recognition_decision: Optional[AssetRecognitionDecision] = Field(
        None,
        description="Recognition decision that led to asset creation"
    )
    policy_confidence: Optional[Decimal] = Field(
        None,
        ge=0,
        le=Decimal("1.00"),
        description="Policy confidence score from the recognition engine"
    )

    @field_validator("asset_type")
    @classmethod
    def validate_asset_type(cls, v: str) -> str:
        v = v.strip().lower()
        valid = set(ASSET_USEFUL_LIFE.keys()) - {"real_estate"}
        if v not in valid:
            raise ValueError(
                f"Invalid asset_type '{v}'. Must be one of: {sorted(valid)}"
            )
        return v

    @field_validator("purchase_date")
    @classmethod
    def validate_purchase_date(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Purchase date cannot be in the future")
        return v

    @field_validator("acquisition_kind")
    @classmethod
    def validate_acquisition_kind(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in ASSET_ACQUISITION_KINDS:
            raise ValueError(
                f"Invalid acquisition_kind '{v}'. Must be one of: {sorted(ASSET_ACQUISITION_KINDS)}"
            )
        return normalized

    @field_validator("prior_owner_usage_years")
    @classmethod
    def validate_prior_owner_usage_years(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        return v.quantize(Decimal("0.01"))

    @field_validator(
        "comparison_amount",
        "income_tax_cost_cap",
        "income_tax_depreciable_base",
        "ifb_rate",
        "policy_confidence",
        "degressive_afa_rate",
    )
    @classmethod
    def quantize_optional_decimal(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        return Decimal(str(v))

    @model_validator(mode="after")
    def auto_useful_life(self):
        if self.useful_life_years is None:
            self.useful_life_years = ASSET_USEFUL_LIFE.get(self.asset_type, 5)
        if self.prior_owner_usage_years is not None:
            self.is_used_asset = True
        if self.acquisition_kind == "used_asset":
            self.is_used_asset = True
        if self.is_used_asset and self.acquisition_kind == "purchase":
            self.acquisition_kind = "used_asset"
        if self.put_into_use_date and self.put_into_use_date < self.purchase_date:
            raise ValueError("put_into_use_date cannot be earlier than purchase_date")
        if self.first_registration_date and self.first_registration_date > self.purchase_date:
            raise ValueError("first_registration_date cannot be later than purchase_date")
        if self.gwg_elected and not self.gwg_eligible:
            raise ValueError("gwg_elected can only be true when gwg_eligible is true")
        if self.degressive_afa_rate is not None and self.depreciation_method != DepreciationMethod.DEGRESSIVE:
            raise ValueError("degressive_afa_rate can only be set when depreciation_method is 'degressive'")
        return self


class AssetResponse(BaseModel):
    """Response schema for non-real-estate assets"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: int
    asset_type: str
    sub_category: Optional[str]
    name: Optional[str]
    purchase_date: date
    purchase_price: Decimal
    building_value: Decimal  # = depreciable value for assets
    depreciation_rate: Decimal
    useful_life_years: Optional[int]
    acquisition_kind: Optional[str] = None
    put_into_use_date: Optional[date] = None
    is_used_asset: bool = False
    first_registration_date: Optional[date] = None
    prior_owner_usage_years: Optional[Decimal] = None
    business_use_percentage: Decimal
    comparison_basis: Optional[ComparisonBasis] = None
    comparison_amount: Optional[Decimal] = None
    gwg_eligible: bool = False
    gwg_elected: bool = False
    depreciation_method: Optional[DepreciationMethod] = None
    degressive_afa_rate: Optional[Decimal] = None
    useful_life_source: Optional[UsefulLifeSource] = None
    income_tax_cost_cap: Optional[Decimal] = None
    income_tax_depreciable_base: Optional[Decimal] = None
    vat_recoverable_status: Optional[VatRecoverableStatus] = None
    ifb_candidate: bool = False
    ifb_rate: Optional[Decimal] = None
    ifb_rate_source: Optional[IfbRateSource] = None
    recognition_decision: Optional[AssetRecognitionDecision] = None
    policy_confidence: Optional[Decimal] = None
    supplier: Optional[str]
    accumulated_depreciation: Decimal
    status: PropertyStatus
    disposal_reason: Optional[str] = None
    kaufvertrag_document_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def annual_depreciation(self) -> Decimal:
        return (self.building_value * self.depreciation_rate).quantize(Decimal("0.01"))

    @computed_field
    @property
    def remaining_value(self) -> Decimal:
        return max(
            self.building_value - self.accumulated_depreciation, Decimal("0")
        ).quantize(Decimal("0.01"))


class AssetListResponse(BaseModel):
    total: int
    assets: list[AssetResponse]
