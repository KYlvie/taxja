"""Authentication schemas"""
from pydantic import BaseModel, EmailStr


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
    business_type: str | None = None  # freiberufler, gewerbetreibende, etc.
    business_industry: str | None = None  # gastronomie, hotel, arzt, etc.
    employer_mode: str | None = "none"  # none, occasional, regular
    employer_region: str | None = None
    language: str | None = None  # de, en, zh — used for verification email language


class UserLogin(BaseModel):
    """User login schema"""
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""
    email: EmailStr
    language: str | None = None


class ResetPasswordRequest(BaseModel):
    """Reset password with token"""
    token: str
    password: str


class UserResponse(BaseModel):
    """User response schema"""
    id: int
    email: str
    name: str
    user_type: str
    vat_status: str | None = None
    gewinnermittlungsart: str | None = None
    employer_mode: str | None = "none"
    employer_region: str | None = None
    two_factor_enabled: bool = False
    is_admin: bool = False
    
    class Config:
        from_attributes = True
