# app/schemas/auth.py
"""
Authentication request and response schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator
import re


# ============================================================================
# REGISTRATION SCHEMAS
# ============================================================================

class RegisterRequest(BaseModel):
    """Request schema for user registration"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    first_name: str = Field(..., min_length=2, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, min_length=2, max_length=100, description="Last name")
    company_name: str = Field(..., min_length=2, max_length=255, description="Company name")
    company_slug: str = Field(..., min_length=2, max_length=100, description="Company slug")

    @validator('password')
    def validate_password(cls, v):
        """Validate password strength"""
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v

    @validator('company_slug')
    def validate_slug(cls, v):
        """Validate slug format"""
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        if v.startswith('-') or v.endswith('-'):
            raise ValueError('Slug cannot start or end with a hyphen')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePassword123!",
                "first_name": "John",
                "last_name": "Doe",
                "company_name": "Acme Corp",
                "company_slug": "acme-corp"
            }
        }


class UserResponse(BaseModel):
    """User data response schema"""
    id: str
    email: str
    first_name: str
    last_name: Optional[str]
    role: str
    email_verified: bool

    class Config:
        from_attributes = True


class TenantResponse(BaseModel):
    """Tenant data response schema"""
    id: str
    name: str
    slug: str
    subscription_status: str
    trial_start_date: Optional[datetime]
    trial_end_date: Optional[datetime]
    trial_days_remaining: Optional[int]

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    """Response schema for successful registration"""
    user: UserResponse
    tenant: TenantResponse
    message: str


# ============================================================================
# EMAIL VERIFICATION SCHEMAS
# ============================================================================

class VerifyEmailRequest(BaseModel):
    """Request schema for email verification"""
    token: str = Field(..., description="Email verification token")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class VerifyEmailResponse(BaseModel):
    """Response schema for email verification"""
    message: str
    user: UserResponse


# ============================================================================
# LOGIN SCHEMAS
# ============================================================================

class LoginRequest(BaseModel):
    """Request schema for user login"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePassword123!"
            }
        }


class TokenResponse(BaseModel):
    """JWT tokens response schema"""
    access_token: str
    refresh_token: str
    expires_in: int = Field(default=1800, description="Access token expiration in seconds")


class LoginResponse(BaseModel):
    """Response schema for successful login"""
    user: UserResponse
    tenant: TenantResponse
    tokens: TokenResponse


# ============================================================================
# REFRESH TOKEN SCHEMAS
# ============================================================================

class RefreshTokenRequest(BaseModel):
    """Request schema for token refresh"""
    refresh_token: str = Field(..., description="Refresh token")


class RefreshTokenResponse(BaseModel):
    """Response schema for token refresh"""
    access_token: str = Field(..., description="New access token")
    expires_in: int = Field(default=1800, description="Token expiration in seconds")


# ============================================================================
# LOGOUT SCHEMAS
# ============================================================================

class LogoutResponse(BaseModel):
    """Response schema for logout"""
    message: str


# ============================================================================
# ERROR RESPONSE SCHEMAS
# ============================================================================

class ErrorDetail(BaseModel):
    """Error detail for validation errors"""
    field: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error response schema"""
    error: dict

    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Validation failed",
                    "details": {
                        "email": "Email already exists",
                        "password": "Password must contain at least one uppercase letter"
                    }
                }
            }
        }