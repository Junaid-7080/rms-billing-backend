"""
FastAPI Dependencies
Reusable dependency functions for authentication, authorization, etc.
Dashboard APIs-il use cheyyan vendi dependencies
"""
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.tenant import Tenant


# Security scheme for Swagger docs
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    JWT token-il ninnu current user fetch cheyyunnu
    
    Dashboard APIs ellam-um authentication venam
    Login cheyyathe dashboard access cheyyan pattilla
    
    Args:
        credentials: Bearer token from Authorization header
        db: Database session
    
    Returns:
        User: Current authenticated user
    
    Raises:
        HTTPException: If token invalid or user not found
    """
    # Token decode cheyyunnu
    token = credentials.credentials
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # JWT decode
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # User ID extract cheyyunnu
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
    except JWTError:
        raise credentials_exception
    
    # Database-il ninnu user fetch
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    # User active aano check
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


def get_current_tenant(
    current_user: User = Depends(get_current_user)
) -> int:
    """
    Current user-nte tenant_id return cheyyunnu
    
    Multi-tenant architecture aanu - prati user oru tenant-il belong cheyyum
    Dashboard data tenant_id use cheythu filter cheyyum
    
    Args:
        current_user: Authenticated user
    
    Returns:
        int: Tenant ID
    
    Raises:
        HTTPException: If user has no tenant
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not associated with any tenant"
        )
    
    return current_user.tenant_id


def get_current_active_tenant(
    tenant_id: int = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Current tenant object fetch cheyyunnu
    Tenant active aano, subscription valid aano check cheyyunnu
    
    Dashboard access cheyyumbol tenant status check cheyyanam:
    - Trial expired aayo?
    - Subscription cancelled aayo?
    - Payment pending aayo?
    
    Args:
        tenant_id: Current tenant ID
        db: Database session
    
    Returns:
        Tenant: Active tenant object
    
    Raises:
        HTTPException: If tenant inactive or subscription issues
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Tenant active check
    if not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant account is inactive"
        )
    
    # Trial period check (if applicable)
    # Production-il proper subscription check implement cheyyum
    
    return tenant


def check_dashboard_access(
    tenant: Tenant = Depends(get_current_active_tenant)
) -> bool:
    """
    Check if tenant has access to dashboard features
    
    Premium features check cheyyunnu:
    - Basic plan: Limited dashboard
    - Pro plan: Full dashboard
    - Enterprise: Advanced analytics
    
    Args:
        tenant: Current tenant
    
    Returns:
        bool: True if has access
    
    Raises:
        HTTPException: If no access to dashboard
    """
    # Subscription-based feature access
    # Production-il implement cheyyendath
    
    # For now, allow all active tenants
    return True


def get_pagination_params(
    skip: int = 0,
    limit: int = 100
) -> dict:
    """
    Pagination parameters for list endpoints
    
    Dashboard-il list APIs-inu pagination venam
    Large datasets handle cheyyan vendi
    
    Args:
        skip: Number of records to skip
        limit: Maximum records to return
    
    Returns:
        dict: Pagination params
    """
    # Limit maximum page size
    if limit > 1000:
        limit = 1000
    
    if skip < 0:
        skip = 0
    
    return {"skip": skip, "limit": limit}


def validate_date_range(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> dict:
    """
    Date range validation for filtered queries
    
    Dashboard-il date filter apply cheyyumbol validation
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    
    Returns:
        dict: Validated date range
    
    Raises:
        HTTPException: If dates invalid
    """
    from datetime import datetime
    
    result = {}
    
    if start_date:
        try:
            result['start_date'] = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid start_date format. Use YYYY-MM-DD"
            )
    
    if end_date:
        try:
            result['end_date'] = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid end_date format. Use YYYY-MM-DD"
            )
    
    # End date should be after start date
    if 'start_date' in result and 'end_date' in result:
        if result['end_date'] < result['start_date']:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end_date must be after start_date"
            )
    
    return result