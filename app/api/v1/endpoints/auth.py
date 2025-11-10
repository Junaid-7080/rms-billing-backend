from app.schemas.response import ErrorResponse
from app.services.auth_service import AuthService
from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.orm import Session
from pydantic import EmailStr
from uuid import uuid4
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.models.user import User, EmailVerification, Session as UserSession
from app.models.tenant import Tenant, Subscription
from app.schemas.auth import (
    RegisterRequest, RegisterResponse,
    VerifyEmailRequest, VerifyEmailResponse,
    LoginRequest, LoginResponse,
    RefreshTokenRequest, RefreshTokenResponse,
    LogoutResponse
)
from app.schemas.auth import VerifyEmailRequest
from app.services.email import send_verification_email


router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user and create tenant",
    description="""
    Register a new user and create a company (tenant). Starts a 14-day free trial.
    
    **Business Logic:**
    1. Validates all input fields
    2. Checks email uniqueness across all users
    3. Checks company slug uniqueness across all tenants
    4. Hashes password using bcrypt (cost factor 12)
    5. Creates tenant with trial subscription
    6. Creates admin user linked to tenant
    7. Generates email verification token (expires in 24 hours)
    8. Sends verification email
    
    **Returns:** User and tenant data (no tokens until email verified)
    
    **Note:** Email must be verified before login is allowed.
    """,
    responses={
        201: {
            "description": "Registration successful",
            "model": RegisterResponse
        },
        400: {
            "description": "Validation error",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "details": {
                                "password": "Password must contain at least one uppercase letter"
                            }
                        }
                    }
                }
            }
        },
        409: {
            "description": "Email or slug already exists",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "EMAIL_EXISTS",
                            "message": "Email already exists",
                            "details": {
                                "email": "This email is already registered"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register new user and create tenant
    
    - **email**: Valid email address (must be unique)
    - **password**: Min 8 chars, 1 uppercase, 1 lowercase, 1 number
    - **firstName**: User's first name (min 2 chars)
    - **lastName**: User's last name (optional)
    - **companyName**: Company name (min 2 chars)
    - **companySlug**: URL-friendly company identifier (lowercase, alphanumeric + hyphens, unique)
    """
    auth_service = AuthService(db)
    return auth_service.register_user(data)


# ============================================================================
# 1.2 VERIFY EMAIL
# ============================================================================

@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify user's email address",
    description="""
    Verify user's email address using verification token sent via email.
    
    **Business Logic:**
    1. Validates token exists and not expired (< 24 hours)
    2. Checks token not already used
    3. Updates user email_verified to true
    4. Marks token as used
    
    **Returns:** Success message and updated user data
    
    **Note:** After verification, user can login to the system.
    """,
    responses={
        200: {
            "description": "Email verified successfully",
            "model": VerifyEmailResponse
        },
        400: {
            "description": "Invalid or expired token",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVALID_TOKEN",
                            "message": "Invalid or expired verification token"
                        }
                    }
                }
            }
        },
        404: {
            "description": "Token not found",
            "model": ErrorResponse
        },
        409: {
            "description": "Email already verified",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "ALREADY_VERIFIED",
                            "message": "Email already verified"
                        }
                    }
                }
            }
        }
    }
)
async def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    """
    Verify email address with token
    
    - **token**: Email verification token (UUID received via email)
    """
    auth_service = AuthService(db)
    return auth_service.verify_email(data)


# ============================================================================
# 1.3 LOGIN
# ============================================================================

@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and return JWT tokens",
    description="""
    Authenticate user and return JWT access and refresh tokens.
    
    **Business Logic:**
    1. Validates email and password
    2. Checks user exists and is active
    3. Verifies email is confirmed
    4. Checks tenant subscription status (trial expiry)
    5. Generates JWT access token (expires in 30 minutes)
    6. Generates JWT refresh token (expires in 7 days)
    7. Creates session record with tokens and device info
    8. Updates last login timestamp
    
    **Returns:** User data, tenant data, and JWT tokens
    
    **Requirements:**
    - Email must be verified
    - Account must be active
    - Trial must not be expired (unless upgraded)
    """,
    responses={
        200: {
            "description": "Login successful",
            "model": LoginResponse
        },
        400: {
            "description": "Missing credentials",
            "model": ErrorResponse
        },
        401: {
            "description": "Invalid credentials",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVALID_CREDENTIALS",
                            "message": "Invalid email or password"
                        }
                    }
                }
            }
        },
        403: {
            "description": "Email not verified or account inactive",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "examples": {
                        "email_not_verified": {
                            "value": {
                                "error": {
                                    "code": "EMAIL_NOT_VERIFIED",
                                    "message": "Please verify your email before logging in"
                                }
                            }
                        },
                        "account_inactive": {
                            "value": {
                                "error": {
                                    "code": "ACCOUNT_INACTIVE",
                                    "message": "Your account has been deactivated"
                                }
                            }
                        }
                    }
                }
            }
        },
        423: {
            "description": "Trial expired and not upgraded",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "TRIAL_EXPIRED",
                            "message": "Your trial has expired. Please upgrade your subscription."
                        }
                    }
                }
            }
        }
    }
)
async def login(
    request: Request,
    data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login and get JWT tokens
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns user data, tenant data, and JWT tokens (access + refresh).
    Access token expires in 30 minutes, refresh token in 7 days.
    """
    auth_service = AuthService(db)
    
    # Get client info for session tracking
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    return auth_service.login_user(data, ip_address, user_agent)

@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Get new access token using refresh token"""
    # 1. Verify refresh token
    try:
        token_data = decode_token(payload.refreshToken)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # 2. Find session by refresh token
    session = db.query(UserSession).filter(
        UserSession.refresh_token == payload.refreshToken,
        UserSession.is_active == True,
        UserSession.expires_at > datetime.utcnow()
    ).first()
    
    # 3. Check if session exists
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired"
        )
    
    # 4. Get user
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 5. Generate new access token
    access_token = create_access_token({
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id),
        "email": user.email,
        "role": user.role
    })
    
    # 6. Update session
    session.access_token = access_token
    session.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "accessToken": access_token,
        "expiresIn": 1800  # 30 minutes
    }


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request, db: Session = Depends(get_db)):
    """Logout user and revoke session"""
    # 1. Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    access_token = auth_header.replace("Bearer ", "")
    
    # 2. Decode token to get user ID
    try:
        token_data = decode_token(access_token)
        user_id = token_data.get("sub")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    # 3. Find and revoke session
    session = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.access_token == access_token,
        UserSession.is_active == True
    ).first()
    
    if session:
        session.is_active = False
        session.revoked_at = datetime.utcnow()
        db.commit()
    
    return {
        "message": "Logged out successfully"
    }


@router.post("/forgot-password")
def forgot_password(email: EmailStr, db: Session = Depends(get_db)):
    """Request password reset"""
    # Find user by email
    user = db.query(User).filter(User.email == email).first()
    
    # Don't reveal if email exists (security best practice)
    if not user:
        return {
            "message": "If the email exists, a password reset link has been sent."
        }
    
    # Generate reset token
    from app.models.user import PasswordReset
    
    reset_token = str(uuid4())
    password_reset = PasswordReset(
        id=str(uuid4()),
        user_id=str(user.id),
        token=reset_token,
        expires_at=datetime.utcnow() + timedelta(hours=1),  # 1 hour expiry
        is_used=False
    )
    db.add(password_reset)
    db.commit()
    
    # Send password reset email
    from app.services.email import send_password_reset_email
    send_password_reset_email(user.email, reset_token)
    
    return {
        "message": "If the email exists, a password reset link has been sent."
    }


@router.post("/reset-password")
def reset_password(
    token: str,
    new_password: str,
    db: Session = Depends(get_db)
):
    """Reset password using token"""
    from app.models.user import PasswordReset
    
    # Find reset token
    reset = db.query(PasswordReset).filter(
        PasswordReset.token == token,
        PasswordReset.is_used == False,
        PasswordReset.expires_at > datetime.utcnow()
    ).first()
    
    if not reset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Get user
    user = db.query(User).filter(User.id == reset.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    user.password_hash = hash_password(new_password)
    user.updated_at = datetime.utcnow()
    
    # Mark token as used
    reset.is_used = True
    reset.used_at = datetime.utcnow()
    
    # Revoke all sessions for security
    db.query(UserSession).filter(
        UserSession.user_id == str(user.id),
        UserSession.is_active == True
    ).update({"is_active": False, "revoked_at": datetime.utcnow()})
    
    db.commit()
    
    return {
        "message": "Password reset successfully. Please log in with your new password."
    }
