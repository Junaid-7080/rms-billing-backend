"""
Authentication API endpoints
Handles user registration, email verification, login, token refresh, and logout
"""
from fastapi import Body
from datetime import datetime, timedelta
from app.core.security import get_current_user
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from app.models.user import User, Session as UserSession, EmailVerification
from app.models.tenant import Tenant, Subscription
from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    VerifyEmailRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from app.services.email import send_verification_email
from app.utils.date import calculate_trial_end_date
import uuid

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Register new user and create tenant (company)
    Starts 14-day free trial
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    # Check if company slug already exists
    existing_tenant = db.query(Tenant).filter(Tenant.slug == request.companySlug).first()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company slug already taken"
        )
    
    try:
        # Create tenant
        tenant_id = uuid.uuid4()
        trial_start = datetime.utcnow()
        trial_end = calculate_trial_end_date(trial_start, days=14)
        
        tenant = Tenant(
            id=tenant_id,
            name=request.companyName,
            slug=request.companySlug,
            email=request.email,
            subscription_status="trial",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            is_trial_used=True,
        )
        db.add(tenant)
        
        # Check if this is the first user for this tenant
        is_first_user = not db.query(User).filter(User.tenant_id == tenant_id).first()
        
        # Create user
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            tenant_id=tenant_id,
            email=request.email,
            password_hash=hash_password(request.password),
            first_name=request.firstName,
            last_name=request.lastName,
            role="admin" if is_first_user else "user",
            email_verified=False,
            is_active=True,
        )
        db.add(user)
        
        # Create subscription
        subscription = Subscription(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            plan_type="trial",
            is_trial=True,
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            status="active",
        )
        db.add(subscription)
        
        # Create email verification token
        verification_token = str(uuid.uuid4())
        verification = EmailVerification(
            id=uuid.uuid4(),
            user_id=user_id,
            token=verification_token,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            is_used=False,
        )
        db.add(verification)
        
        db.commit()
        db.refresh(user)
        db.refresh(tenant)
        
        # Send verification email
        await send_verification_email(user.email, verification_token)
        
        # Calculate trial days remaining
        trial_days_remaining = (trial_end - trial_start).days
        
        return RegisterResponse(
            user={
                "id": str(user.id),
                "email": user.email,
                "firstName": user.first_name,
                "lastName": user.last_name,
                "role": user.role,
                "emailVerified": user.email_verified,
            },
            tenant={
                "id": str(tenant.id),
                "name": tenant.name,
                "slug": tenant.slug,
                "subscriptionStatus": tenant.subscription_status,
                "trialStartDate": trial_start.isoformat(),
                "trialEndDate": trial_end.isoformat(),
                "trialDaysRemaining": trial_days_remaining,
            },
            message="Registration successful. Please check your email to verify your account.",
            verificationToken=verification_token
        )
        
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity error. Please try again."
        )

@router.post("/login", response_model=LoginResponse)
async def login(
    request_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> Any:
    """
    Authenticate user and return JWT tokens
    """
    # Find user
    user = db.query(User).filter(
        User.email == request_data.email,
        User.is_active == True
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(request_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Get tenant
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check trial expiration
    trial_days_remaining = None
    if tenant.subscription_status == "trial":
        if tenant.trial_end_date < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Trial period has expired. Please upgrade your subscription."
            )
        trial_days_remaining = (tenant.trial_end_date - datetime.utcnow()).days
    
    # Generate tokens
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "tenant_id": str(tenant.id),
            "email": user.email,
            "role": user.role,
        }
    )
    
    refresh_token = create_refresh_token(
        data={
            "sub": str(user.id),
            "tenant_id": str(tenant.id),
            "type": "refresh",
        }
    )
    
    # Create session
    session = UserSession(
        id=uuid.uuid4(),
        user_id=user.id,
        refresh_token=refresh_token,
        access_token=access_token,
        expires_at=datetime.utcnow() + timedelta(days=7),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        is_active=True,
    )
    db.add(session)
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    
    db.commit()
    
    return LoginResponse(
        user={
            "id": str(user.id),
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "role": user.role,
            "emailVerified": user.email_verified,
        },
        tenant={
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "subscriptionStatus": tenant.subscription_status,
            "trialStartDate": tenant.trial_start_date.isoformat() if tenant.trial_start_date else None,
            "trialEndDate": tenant.trial_end_date.isoformat() if tenant.trial_end_date else None,
            "trialDaysRemaining": trial_days_remaining,
        },
        tokens={
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresIn": 1800,
        }
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Get new access token using refresh token
    """
    # Verify refresh token
    try:
        payload = verify_token(request.refreshToken)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Find session
    session = db.query(UserSession).filter(
        UserSession.refresh_token == request.refreshToken,
        UserSession.is_active == True,
        UserSession.expires_at > datetime.utcnow()
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired"
        )
    
    # Get user
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Generate new access token
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id),
            "email": user.email,
            "role": user.role,
        }
    )
    
    # Update session
    session.access_token = access_token
    db.commit()
    
    return TokenResponse(
        accessToken=access_token,
        expiresIn=1800
    )


@router.post("/logout")
async def logout(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Logout user and revoke session
    """
    # Find and revoke session
    session = db.query(UserSession).filter(
        UserSession.refresh_token == request.refreshToken
    ).first()
    
    if session:
        session.is_active = False
        session.revoked_at = datetime.utcnow()
        db.commit()
    
    return {"message": "Logged out successfully"}

# =============================================================
#  2.6 CHANGE USER ROLE (Admin Only)
# =============================================================

@router.put("/users/{user_id}/change-role")
async def change_role(
    user_id: str,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)   # ⬅️ uses JWT auth
):
    """
    Change a user's role.
    Allowed roles: admin, manager, user
    """

    # Ensure logged-in user is admin
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admin users can change roles"
        )

    allowed_roles = ["admin", "manager", "user"]

    new_role = data.get("role")
    if new_role not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Allowed roles: {allowed_roles}"
        )

    # Find user to update
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    old_role = user.role
    user.role = new_role
    db.commit()

    return {
        "message": "User role updated successfully",
        "userId": str(user.id),
        "oldRole": old_role,
        "newRole": new_role
    }
