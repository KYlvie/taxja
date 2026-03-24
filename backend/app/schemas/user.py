"""User schemas for request/response validation."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import (
    Gewinnermittlungsart,
    SelfEmployedType,
    UserType,
    VatStatus,
)

TaxProfileField = Literal["vat_status", "gewinnermittlungsart"]


class TaxProfileCompleteness(BaseModel):
    """Shared completeness contract for asset automation entrypoints."""

    is_complete_for_asset_automation: bool
    missing_fields: list[TaxProfileField] = Field(default_factory=list)
    source: Literal["persisted_user_profile"] = "persisted_user_profile"
    contract_version: Literal["v1"] = "v1"


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    user_type: UserType


class UserRegister(UserBase):
    """User registration schema."""

    password: str = Field(..., min_length=8, max_length=100)
    tax_number: Optional[str] = Field(None, max_length=50)
    vat_number: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not v or "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower()


class UserProfileUpdate(BaseModel):
    """Profile update schema matching the flattened frontend payload."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tax_number: Optional[str] = Field(None, max_length=50)
    vat_number: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    user_type: Optional[UserType] = None
    business_type: Optional[SelfEmployedType] = None
    business_name: Optional[str] = Field(None, max_length=255)
    business_industry: Optional[str] = Field(None, max_length=50)
    vat_status: Optional[VatStatus] = None
    gewinnermittlungsart: Optional[Gewinnermittlungsart] = None
    user_roles: Optional[list[str]] = None
    commuting_distance_km: Optional[int] = Field(None, ge=0, le=1000)
    public_transport_available: Optional[bool] = None
    num_children: Optional[int] = Field(None, ge=0, le=50)
    is_single_parent: Optional[bool] = None
    family_info: Optional[dict] = None
    commuting_info: Optional[dict] = None
    home_office_eligible: Optional[bool] = None
    telearbeit_days: Optional[int] = Field(None, ge=0, le=366)
    employer_telearbeit_pauschale: Optional[Decimal] = Field(None, ge=0)
    employer_mode: Optional[str] = Field(None, pattern="^(none|occasional|regular)$")
    employer_region: Optional[str] = Field(None, max_length=100)
    language: Optional[str] = Field(None, pattern="^(de|en|zh|fr|ru|hu|pl|tr|bs)$")

    @field_validator("user_roles")
    @classmethod
    def validate_user_roles(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        allowed_roles = {"employee", "landlord", "self_employed", "gmbh"}
        normalized = []
        for role in v:
            if role not in allowed_roles:
                raise ValueError(f"Invalid user role: {role}")
            if role not in normalized:
                normalized.append(role)
        return normalized

    @field_validator("business_type", "vat_status", "gewinnermittlungsart", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v


class UserResponse(UserBase):
    """User response schema."""

    id: int
    tax_number: Optional[str] = None
    vat_number: Optional[str] = None
    address: Optional[str] = None
    family_info: dict = Field(default_factory=dict)
    commuting_info: dict = Field(default_factory=dict)
    home_office_eligible: bool = False
    telearbeit_days: Optional[int] = None
    employer_telearbeit_pauschale: Optional[Decimal] = None
    employer_mode: str = "none"
    employer_region: Optional[str] = None
    language: str = "de"
    two_factor_enabled: bool = False
    disclaimer_accepted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):
    """Flattened frontend-facing profile response."""

    id: int
    email: EmailStr
    name: str
    address: Optional[str] = None
    tax_number: Optional[str] = None
    vat_number: Optional[str] = None
    user_type: str
    user_roles: list[str] = Field(default_factory=list)
    business_type: Optional[str] = None
    business_name: Optional[str] = None
    business_industry: Optional[str] = None
    vat_status: Optional[str] = None
    gewinnermittlungsart: Optional[str] = None
    tax_profile_completeness: TaxProfileCompleteness
    employer_mode: str = "none"
    employer_region: Optional[str] = None
    commuting_distance_km: int = 0
    public_transport_available: bool = True
    telearbeit_days: int = 0
    employer_telearbeit_pauschale: float = 0
    num_children: int = 0
    is_single_parent: bool = False
    language: str = "de"
    two_factor_enabled: bool = False
    home_office_eligible: bool = False
    disclaimer_accepted: bool = False


class UserRegisterResponse(BaseModel):
    """User registration response with JWT token."""

    user: UserResponse
    access_token: str
    token_type: str = "bearer"
