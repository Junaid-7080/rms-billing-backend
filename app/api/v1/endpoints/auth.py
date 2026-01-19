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
from app.models.role import Role
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
    
    # Generate slug from company name
    import re
    company_slug = re.sub(r'[^a-z0-9]+', '-', request.companyName.lower()).strip('-')
    
    # Check if company slug already exists
    existing_tenant = db.query(Tenant).filter(Tenant.slug == company_slug).first()
    if existing_tenant:
        # Add a random suffix to make it unique
        import random
        company_slug = f"{company_slug}-{random.randint(1000, 9999)}"
    
    try:
        # Create tenant
        tenant_id = uuid.uuid4()
        trial_start = datetime.utcnow()
        trial_end = calculate_trial_end_date(trial_start, days=14)
        
        tenant = Tenant(
            id=tenant_id,
            name=request.companyName,
            slug=company_slug,
            email=request.email,
            subscription_status="trial",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            is_trial_used=True,
        )
        db.add(tenant)
        
        # Create default roles for the tenant
        admin_role_id = uuid.uuid4()
        admin_role = Role(
            id=admin_role_id,
            tenant_id=tenant_id,
            name="admin",
            description="Super admin role with all permissions",
            permissions={},
            is_system=True,
            is_active=True
        )
        db.add(admin_role)

        user_role_obj = Role(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name="user",
            description="Regular user role with limited access",
            permissions={},
            is_system=True,
            is_active=True
        )
        db.add(user_role_obj)

        # Determine which role to assign
        # If roleId is provided, copy that role's details to create a new role for this tenant
        assigned_role_id = admin_role_id
        assigned_role_name = "admin"
        
        if hasattr(request, 'roleId') and request.roleId:
            # Fetch the source role from any tenant
            source_role = db.query(Role).filter(Role.id == request.roleId).first()
            
            if source_role:
                # Create a copy of this role for the new tenant
                custom_role_id = uuid.uuid4()
                custom_role = Role(
                    id=custom_role_id,
                    tenant_id=tenant_id,
                    name=source_role.name,
                    description=source_role.description or f"{source_role.name} role",
                    permissions=source_role.permissions or {},
                    is_system=False,
                    is_active=True
                )
                db.add(custom_role)
                
                assigned_role_id = custom_role_id
                assigned_role_name = source_role.name
        
        # Create user
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            tenant_id=tenant_id,
            email=request.email,
            password_hash=hash_password(request.password),
            first_name=request.firstName,
            last_name=request.lastName,
            role=assigned_role_name,
            role_id=assigned_role_id,
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
                "roleId": str(user.role_id) if user.role_id else None,
                "roleName": user.user_role.name if user.user_role else None,
                "isActive": user.is_active,
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
        User.email == request_data.email
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact your administrator."
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
    
    # Trial check removed - Login always allowed
    trial_days_remaining = None
    if tenant.trial_end_date:
        trial_days_remaining = (tenant.trial_end_date - datetime.utcnow()).days
    
    # Generate tokens (Allow login even if trial expired)
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
            "roleId": str(user.role_id) if user.role_id else None,
            "roleName": user.user_role.name if user.user_role else None,
            "isActive": user.is_active,
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
