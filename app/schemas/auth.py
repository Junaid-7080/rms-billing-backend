"""
Authentication Pydantic schemas
Request and response models for authentication endpoints
"""
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, validator
import re


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    firstName: str = Field(..., min_length=2)
    lastName: Optional[str] = Field(None, min_length=2)
    companyName: str = Field(..., min_length=2)
    roleId: Optional[UUID] = None  # Optional: copy role from existing role
    
    @validator('password')
    def validate_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        return v
    
class UserResponse(BaseModel):
    id: str
    email: str
    firstName: str
    lastName: Optional[str]
    role: Optional[str]
    roleId: Optional[str]
    roleName: Optional[str]
    isActive: bool
    emailVerified: bool


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    subscriptionStatus: str
    trialStartDate: Optional[str]
    trialEndDate: Optional[str]
    trialDaysRemaining: Optional[int]


class RegisterResponse(BaseModel):
    user: UserResponse
    tenant: TenantResponse
    message: str
    verificationToken: str  # Add this field


class VerifyEmailRequest(BaseModel):
    token: str

class LoginRequest(BaseModel):
    email: str
    password: str



class TokensResponse(BaseModel):
    accessToken: str
    refreshToken: str
    expiresIn: int


class LoginResponse(BaseModel):
    user: UserResponse
    tenant: TenantResponse
    tokens: TokensResponse


class RefreshTokenRequest(BaseModel):
    refreshToken: str


class TokenResponse(BaseModel):
    accessToken: str
    expiresIn: int

class ChangeRoleResponse(BaseModel):
    message: str
    userId: str
    oldRole: str
    newRole: str