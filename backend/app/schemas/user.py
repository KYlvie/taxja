"""User schemas for request/response validation"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.models.user import UserType


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    user_type: UserType


class UserRegister(UserBase):
    """User registration schema"""
    password: str = Field(..., min_length=8, max_length=100)
    tax_number: Optional[str] = Field(None, max_length=50)
    vat_number: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format"""
        # EmailStr already validates basic format, but we can add custom rules
        if not v or '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower()


class UserProfileUpdate(BaseModel):
    """User profile update schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tax_number: Optional[str] = Field(None, max_length=50)
    vat_number: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    user_type: Optional[UserType] = None
    family_info: Optional[dict] = None
    commuting_info: Optional[dict] = None
    home_office_eligible: Optional[bool] = None
    language: Optional[str] = Field(None, pattern='^(de|en|zh)$')


class UserResponse(UserBase):
    """User response schema"""
    id: int
    tax_number: Optional[str] = None
    vat_number: Optional[str] = None
    address: Optional[str] = None
    family_info: dict = {}
    commuting_info: dict = {}
    home_office_eligible: bool = False
    language: str = "de"
    two_factor_enabled: bool = False
    disclaimer_accepted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserRegisterResponse(BaseModel):
    """User registration response with JWT token"""
    user: UserResponse
    access_token: str
    token_type: str = "bearer"
