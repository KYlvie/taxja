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


class UserLogin(BaseModel):
    """User login schema"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User response schema"""
    id: int
    email: str
    name: str
    user_type: str
    
    class Config:
        from_attributes = True
