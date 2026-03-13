"""
Tax Configuration Schemas

Pydantic schemas for tax configuration API requests and responses.
"""

from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


class TaxBracketCreate(BaseModel):
    """Schema for creating a tax bracket"""
    lower_limit: Decimal = Field(..., description="Lower limit of bracket in EUR")
    upper_limit: Decimal = Field(..., description="Upper limit of bracket in EUR")
    rate: Decimal = Field(..., ge=0, le=1, description="Tax rate (0-1)")
    order: int = Field(..., ge=0, description="Order of bracket")


class TaxBracketResponse(TaxBracketCreate):
    """Schema for tax bracket response"""
    id: int
    
    class Config:
        orm_mode = True


class TaxConfigurationCreate(BaseModel):
    """Schema for creating a new tax configuration"""
    tax_year: int = Field(..., ge=2020, le=2100, description="Tax year")
    template_year: Optional[int] = Field(None, description="Year to copy from")


class TaxConfigurationUpdate(BaseModel):
    """Schema for updating tax configuration"""
    exemption_amount: Optional[Decimal] = Field(None, description="Tax exemption amount")
    tax_brackets: Optional[List[Dict[str, Any]]] = Field(None, description="Tax brackets")
    vat_standard_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    vat_residential_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    vat_small_business_threshold: Optional[Decimal] = Field(None, ge=0)
    vat_tolerance_threshold: Optional[Decimal] = Field(None, ge=0)
    svs_pension_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    svs_health_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    svs_accident_fixed: Optional[Decimal] = Field(None, ge=0)
    svs_supplementary_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    svs_gsvg_min_base_monthly: Optional[Decimal] = Field(None, ge=0)
    svs_gsvg_min_income_yearly: Optional[Decimal] = Field(None, ge=0)
    svs_neue_min_monthly: Optional[Decimal] = Field(None, ge=0)
    svs_max_base_monthly: Optional[Decimal] = Field(None, ge=0)
    home_office_deduction: Optional[Decimal] = Field(None, ge=0)
    child_deduction_monthly: Optional[Decimal] = Field(None, ge=0)
    single_parent_deduction: Optional[Decimal] = Field(None, ge=0)
    commuting_allowance_config: Optional[Dict[str, Any]] = None
    deduction_config: Optional[Dict[str, Any]] = None


class TaxConfigurationResponse(BaseModel):
    """Schema for tax configuration response"""
    id: int
    tax_year: int
    exemption_amount: Decimal
    tax_brackets: List[TaxBracketResponse]
    vat_standard_rate: Decimal
    vat_residential_rate: Decimal
    vat_small_business_threshold: Decimal
    vat_tolerance_threshold: Decimal
    svs_pension_rate: Decimal
    svs_health_rate: Decimal
    svs_accident_fixed: Decimal
    svs_supplementary_rate: Decimal
    svs_gsvg_min_base_monthly: Decimal
    svs_gsvg_min_income_yearly: Decimal
    svs_neue_min_monthly: Decimal
    svs_max_base_monthly: Decimal
    home_office_deduction: Decimal
    child_deduction_monthly: Decimal
    single_parent_deduction: Decimal
    commuting_allowance_config: Optional[Dict[str, Any]]
    deduction_config: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
