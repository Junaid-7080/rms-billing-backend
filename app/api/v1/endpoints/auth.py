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
from app.services.email import send_verification_email

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)):
    # 1️⃣ Check email uniqueness
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"email": "Email already exists"}
        )

    # 2️⃣ Check company slug uniqueness
    if db.query(Tenant).filter(Tenant.slug == payload.companySlug).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"companySlug": "Company slug already exists"}
        )

    # 3️⃣ Create tenant (14-day trial)
    tenant_id = str(uuid4())
    trial_start = datetime.utcnow()
    trial_end = trial_start + timedelta(days=14)

    tenant = Tenant(
        id=tenant_id,
        name=payload.companyName,
        slug=payload.companySlug,
        subscription_status="trial",
        trial_start_date=trial_start,
        trial_end_date=trial_end,
        is_trial_used=True,
    )
    db.add(tenant)

    # 4️⃣ Hash password
    password_hash = hash_password(payload.password)

    # 5️⃣ Create user (admin)
    user_id = str(uuid4())
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=payload.email,
        password_hash=password_hash,
        first_name=payload.firstName,
        last_name=payload.lastName,
        role="admin",
        email_verified=False,
        created_at=datetime.utcnow(),
    )
    db.add(user)

    # 6️⃣ Create subscription record
    subscription = Subscription(
        id=str(uuid4()),
        tenant_id=tenant_id,
        plan_type="trial",
        is_trial=True,
        trial_start_date=trial_start,
        trial_end_date=trial_end,
    )
    db.add(subscription)

    # 7️⃣ Create email verification token
    token_id = str(uuid4())
    verification = EmailVerification(
        id=token_id,
        user_id=user_id,
        token=str(uuid4()),
        expires_at=datetime.utcnow() + timedelta(hours=24),
        is_used=False,
    )
    db.add(verification)
    db.commit()
    db.refresh(user)
    db.refresh(tenant)

    # 8️⃣ Send verification email
    send_verification_email(user.email, verification.token)

    # 9️⃣ Response
    trial_days_remaining = (trial_end - trial_start).days

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "role": user.role,
            "emailVerified": user.email_verified,
        },
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "subscriptionStatus": tenant.subscription_status,
            "trialStartDate": tenant.trial_start_date,
            "trialEndDate": tenant.trial_end_date,
            "trialDaysRemaining": trial_days_remaining,
        },
        "message": "Registration successful. Please check your email to verify your account."
    }


@router.post("/verify-email", response_model=VerifyEmailResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify user's email address using verification token"""
    # 1. Find verification record by token
    verification = db.query(EmailVerification).filter(
        EmailVerification.token == payload.token,
        EmailVerification.is_used == False,
        EmailVerification.expires_at > datetime.utcnow()
    ).first()
    
    # 2. Check if token exists and valid
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    # 3. Get associated user
    user = db.query(User).filter(User.id == verification.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 4. Check if already verified
    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already verified"
        )
    
    # 5. Update user
    user.email_verified = True
    user.email_verified_at = datetime.utcnow()
    
    # 6. Mark token as used
    verification.is_used = True
    verification.used_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": "Email verified successfully. You can now log in.",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "emailVerified": user.email_verified
        }
    }


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate user and return JWT tokens"""
    # 1. Find user by email
    user = db.query(User).filter(
        User.email == payload.email,
        User.is_active == True
    ).first()
    
    # 2. Check if user exists
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # 3. Verify password
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # 4. Check if email is verified
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your email."
        )
    
    # 5. Get user's tenant
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # 6. Check subscription status
    if tenant.subscription_status == 'expired':
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Trial expired. Please upgrade to continue."
        )
    
    # Calculate trial days remaining
    trial_days_remaining = 0
    if tenant.subscription_status == 'trial' and tenant.trial_end_date:
        days_left = (tenant.trial_end_date - datetime.utcnow()).days
        trial_days_remaining = max(0, days_left)
    
    # 7. Generate JWT tokens
    access_token = create_access_token({
        "sub": str(user.id),
        "tenant_id": str(tenant.id),
        "email": user.email,
        "role": user.role
    })
    
    refresh_token = create_refresh_token({
        "sub": str(user.id),
        "tenant_id": str(tenant.id),
        "type": "refresh"
    })
    
    # 8. Create session record
    session = UserSession(
        id=str(uuid4()),
        user_id=str(user.id),
        refresh_token=refresh_token,
        access_token=access_token,
        expires_at=datetime.utcnow() + timedelta(days=7),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        is_active=True
    )
    db.add(session)
    
    # 9. Update last login
    user.last_login_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "role": user.role,
            "emailVerified": user.email_verified
        },
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "subscriptionStatus": tenant.subscription_status,
            "trialDaysRemaining": trial_days_remaining,
            "trialEndDate": tenant.trial_end_date.isoformat() if tenant.trial_end_date else None
        },
        "tokens": {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresIn": 1800  # 30 minutes
        }
    }


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
