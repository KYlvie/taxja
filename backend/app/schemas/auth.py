"""Authentication schemas"""
import re
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import Gewinnermittlungsart, SelfEmployedType, VatStatus


def _validate_password_strength(password: str) -> str:
    """Validate password meets minimum strength requirements."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    return password


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT token payload"""
    sub: str  # subject (user email or ID)
    exp: int  # expiration timestamp


class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str


class UserRegister(BaseModel):
    """User registration schema"""
    email: EmailStr
    name: str
    password: str
    user_type: str  # EMPLOYEE, LANDLORD, SELF_EMPLOYED, SMALL_BUSINESS, MIXED
    user_roles: list[str] | None = None
    business_type: SelfEmployedType | None = None  # freiberufler, gewerbetreibende, etc.
    business_name: str | None = Field(None, max_length=255)
    business_industry: str | None = None  # gastronomie, hotel, arzt, etc.
    tax_number: str | None = Field(None, max_length=50)
    vat_number: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    vat_status: VatStatus | None = None
    gewinnermittlungsart: Gewinnermittlungsart | None = None
    employer_mode: str | None = "none"  # none, occasional, regular
    employer_region: str | None = None
    commuting_distance_km: int | None = Field(None, ge=0, le=1000)
    public_transport_available: bool | None = None
    telearbeit_days: int | None = Field(None, ge=0, le=366)
    employer_telearbeit_pauschale: Decimal | None = Field(None, ge=0)
    num_children: int | None = Field(None, ge=0, le=50)
    is_single_parent: bool | None = None
    language: str | None = None  # de, en, zh, fr, ru, hu, pl, tr, bs — used for verification email language

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)

    @field_validator("user_roles")
    @classmethod
    def validate_user_roles(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        allowed_roles = {"employee", "landlord", "self_employed", "gmbh"}
        normalized: list[str] = []
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


class UserLogin(BaseModel):
    """User login schema"""
    email: EmailStr
    password: str
    two_factor_code: str | None = None


class GoogleLoginRequest(BaseModel):
    """Google login request carrying the Google Identity credential JWT."""
    credential: str = Field(..., min_length=10)


class TwoFactorVerifyRequest(BaseModel):
    """Request body for 2FA code verification"""
    code: str = Field(..., min_length=6, max_length=6)


class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""
    email: EmailStr
    language: str | None = None


class ResetPasswordRequest(BaseModel):
    """Reset password with token"""
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class UserResponse(BaseModel):
    """User response schema"""
    id: int
    email: str
    name: str
    user_type: str
    user_roles: list[str] = Field(default_factory=list)
    business_type: str | None = None
    business_name: str | None = None
    business_industry: str | None = None
    vat_status: str | None = None
    gewinnermittlungsart: str | None = None
    employer_mode: str | None = "none"
    employer_region: str | None = None
    commuting_distance_km: int = 0
    public_transport_available: bool = True
    telearbeit_days: int = 0
    employer_telearbeit_pauschale: float = 0
    num_children: int = 0
    is_single_parent: bool = False
    language: str = "de"
    two_factor_enabled: bool = False
    is_admin: bool = False
    
    class Config:
        from_attributes = True
