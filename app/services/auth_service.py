# app/services/auth_service.py
"""
Authentication service with business logic
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
import bcrypt
import jwt

from app.models.user import User, Session as UserSession, EmailVerification
from app.models.tenant import Tenant, Subscription
from app.schemas.auth import (
    RegisterRequest, 
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    UserResponse,
    TenantResponse,
    TokenResponse,
    VerifyEmailRequest,
    VerifyEmailResponse
)
from app.core.config import settings


class AuthService:
    """Service class for authentication operations"""

    def __init__(self, db: Session):
        self.db = db

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt with cost factor 12"""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    def _generate_jwt_token(
        self, 
        user_id: uuid.UUID, 
        tenant_id: uuid.UUID,
        email: str,
        role: str,
        token_type: str = "access",
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Generate JWT token"""
        if expires_delta is None:
            expires_delta = timedelta(minutes=30) if token_type == "access" else timedelta(days=7)
        
        expire = datetime.utcnow() + expires_delta
        
        payload = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "email": email,
            "role": role,
            "type": token_type,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def _calculate_trial_days_remaining(self, trial_end_date: Optional[datetime]) -> Optional[int]:
        """Calculate days remaining in trial"""
        if not trial_end_date:
            return None
        
        remaining = (trial_end_date - datetime.utcnow()).days
        return max(0, remaining)

    def _send_verification_email(self, email: str, token: str):
        """Send email verification email (placeholder)"""
        # TODO: Implement actual email sending
        verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        print(f"Verification email would be sent to {email}")
        print(f"Verification link: {verification_link}")

    # ========================================================================
    # REGISTRATION
    # ========================================================================

    def register_user(self, data: RegisterRequest) -> RegisterResponse:
        """
        Register new user and create tenant
        Business logic as per specification
        """
        # 1. Check email uniqueness
        existing_user = self.db.query(User).filter(User.email == data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "EMAIL_EXISTS",
                        "message": "Email already exists",
                        "details": {"email": "This email is already registered"}
                    }
                }
            )

        # 2. Check slug uniqueness
        existing_tenant = self.db.query(Tenant).filter(Tenant.slug == data.company_slug).first()
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "SLUG_EXISTS",
                        "message": "Company slug already exists",
                        "details": {"company_slug": "This company slug is already taken"}
                    }
                }
            )

        # 3. Hash password
        password_hash = self._hash_password(data.password)

        # 4. Create tenant
        trial_start = datetime.utcnow()
        trial_end = trial_start + timedelta(days=14)
        
        tenant = Tenant(
            id=uuid.uuid4(),
            name=data.company_name,
            slug=data.company_slug,
            email=data.email,
            subscription_status="trial",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            is_trial_used=True,
            invoice_count=0,
            customer_count=0,
            user_count=1,
            storage_used_mb=0
        )

        # 5. Create user
        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=data.email,
            password_hash=password_hash,
            first_name=data.first_name,
            last_name=data.last_name,
            role="admin",
            email_verified=False,
            is_active=True
        )

        # 6. Create subscription
        subscription = Subscription(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            plan_type="trial",
            is_trial=True,
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            status="active"
        )

        # 7. Create email verification token
        verification_token = str(uuid.uuid4())
        token_expires = datetime.utcnow() + timedelta(hours=24)
        
        email_verification = EmailVerification(
            id=uuid.uuid4(),
            user_id=user.id,
            token=verification_token,
            expires_at=token_expires,
            is_used=False
        )

        # 8. Save to database
        try:
            self.db.add(tenant)
            self.db.add(user)
            self.db.add(subscription)
            self.db.add(email_verification)
            self.db.commit()
            self.db.refresh(tenant)
            self.db.refresh(user)
        except IntegrityError as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "DATABASE_ERROR",
                        "message": "Failed to create account",
                        "details": {"database": str(e)}
                    }
                }
            )

        # 9. Send verification email
        self._send_verification_email(data.email, verification_token)

        # 10. Prepare response
        user_response = UserResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role,
            email_verified=user.email_verified
        )

        tenant_response = TenantResponse(
            id=str(tenant.id),
            name=tenant.name,
            slug=tenant.slug,
            subscription_status=tenant.subscription_status,
            trial_start_date=tenant.trial_start_date,
            trial_end_date=tenant.trial_end_date,
            trial_days_remaining=self._calculate_trial_days_remaining(tenant.trial_end_date)
        )

        return RegisterResponse(
            user=user_response,
            tenant=tenant_response,
            message="Registration successful. Please check your email to verify your account."
        )

    # ========================================================================
    # EMAIL VERIFICATION
    # ========================================================================

    def verify_email(self, data: VerifyEmailRequest) -> VerifyEmailResponse:
        """
        Verify user's email address
        Business logic as per specification
        """
        # 1. Find verification record
        verification = self.db.query(EmailVerification).filter(
            EmailVerification.token == data.token,
            EmailVerification.is_used == False,
            EmailVerification.expires_at > datetime.utcnow()
        ).first()

        if not verification:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_TOKEN",
                        "message": "Invalid or expired verification token"
                    }
                }
            )

        # 2. Get user
        user = self.db.query(User).filter(User.id == verification.user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "USER_NOT_FOUND",
                        "message": "User not found"
                    }
                }
            )

        # 3. Check if already verified
        if user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "ALREADY_VERIFIED",
                        "message": "Email already verified"
                    }
                }
            )

        # 4. Update user
        user.email_verified = True
        user.email_verified_at = datetime.utcnow()

        # 5. Mark token as used
        verification.is_used = True
        verification.used_at = datetime.utcnow()

        # 6. Save changes
        try:
            self.db.commit()
            self.db.refresh(user)
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": {
                        "code": "DATABASE_ERROR",
                        "message": "Failed to verify email"
                    }
                }
            )

        # 7. Prepare response
        user_response = UserResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role,
            email_verified=user.email_verified
        )

        return VerifyEmailResponse(
            message="Email verified successfully. You can now log in.",
            user=user_response
        )

    # ========================================================================
    # LOGIN
    # ========================================================================

    def login_user(
        self, 
        data: LoginRequest, 
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> LoginResponse:
        """
        Authenticate user and return JWT tokens
        Business logic as per specification
        """
        # 1. Find user with tenant
        user = self.db.query(User).filter(User.email == data.email).first()

        # 2. Verify user exists
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "INVALID_CREDENTIALS",
                        "message": "Invalid email or password"
                    }
                }
            )

        # 3. Verify password
        if not self._verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "INVALID_CREDENTIALS",
                        "message": "Invalid email or password"
                    }
                }
            )

        # 4. Check email verified
        if not user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "EMAIL_NOT_VERIFIED",
                        "message": "Please verify your email before logging in"
                    }
                }
            )

        # 5. Check user active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "ACCOUNT_INACTIVE",
                        "message": "Your account has been deactivated"
                    }
                }
            )

        # 6. Get tenant
        tenant = self.db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": {
                        "code": "TENANT_NOT_FOUND",
                        "message": "Company not found"
                    }
                }
            )

        # 7. Check subscription status
        if tenant.subscription_status == "trial":
            days_remaining = self._calculate_trial_days_remaining(tenant.trial_end_date)
            if days_remaining == 0:
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail={
                        "error": {
                            "code": "TRIAL_EXPIRED",
                            "message": "Your trial has expired. Please upgrade your subscription."
                        }
                    }
                )

        # 8. Generate tokens
        access_token = self._generate_jwt_token(
            user.id, tenant.id, user.email, user.role, "access"
        )
        refresh_token = self._generate_jwt_token(
            user.id, tenant.id, user.email, user.role, "refresh"
        )

        # 9. Create session
        session_expires = datetime.utcnow() + timedelta(days=7)
        session = UserSession(
            id=uuid.uuid4(),
            user_id=user.id,
            refresh_token=refresh_token,
            access_token=access_token,
            expires_at=session_expires,
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True
        )

        # 10. Update last login
        user.last_login_at = datetime.utcnow()

        # 11. Save to database
        try:
            self.db.add(session)
            self.db.commit()
            self.db.refresh(user)
            self.db.refresh(tenant)
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": {
                        "code": "DATABASE_ERROR",
                        "message": "Failed to create session"
                    }
                }
            )

        # 12. Prepare response
        user_response = UserResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role,
            email_verified=user.email_verified
        )

        tenant_response = TenantResponse(
            id=str(tenant.id),
            name=tenant.name,
            slug=tenant.slug,
            subscription_status=tenant.subscription_status,
            trial_start_date=tenant.trial_start_date,
            trial_end_date=tenant.trial_end_date,
            trial_days_remaining=self._calculate_trial_days_remaining(tenant.trial_end_date)
        )

        tokens_response = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=1800  # 30 minutes
        )

        return LoginResponse(
            user=user_response,
            tenant=tenant_response,
            tokens=tokens_response
        )