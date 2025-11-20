from datetime import date
from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.tenant import Tenant


# -------------------------
# TENANT DEPENDENCIES
# -------------------------
def get_current_tenant(
    current_user: User = Depends(get_current_user)
) -> int:
    """
    Get current user's tenant ID
    
    Raises:
        HTTPException: If user is not associated with any tenant
    """
    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not associated with any tenant"
        )
    return tenant_id


def get_current_active_tenant(
    tenant_id: int = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Get current active tenant with subscription checks
    
    Raises:
        HTTPException: If tenant is inactive, expired, or has payment pending
    """
    # Fetch tenant from database
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check if tenant is active
    if not getattr(tenant, "is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant account is inactive"
        )
    
    today = date.today()
    
    # Check trial period
    trial_end_date = getattr(tenant, "trial_end_date", None)
    if trial_end_date and trial_end_date < today:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant trial period has expired"
        )
    
    # Check subscription
    subscription_end_date = getattr(tenant, "subscription_end_date", None)
    if subscription_end_date and subscription_end_date < today:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant subscription has expired"
        )
    
    # Check payment status
    if getattr(tenant, "is_payment_pending", False):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment pending for this tenant"
        )
    
    return tenant


def get_tenant_user(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_active_tenant)
) -> tuple[User, Tenant]:
    """
    Get both current user and tenant in one dependency
    Useful for routes that need both
    """
    return current_user, tenant


# -------------------------
# TENANT ROLE-BASED ACCESS
# -------------------------
def require_tenant_admin(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_active_tenant)
) -> User:
    """
    Require user to be admin of their tenant
    """
    # Check if user is tenant admin
    is_tenant_admin = getattr(current_user, "is_tenant_admin", False)
    
    if not is_tenant_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admin privileges required"
        )
    
    return current_user


def require_tenant_owner(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_active_tenant)
) -> User:
    """
    Require user to be the owner of their tenant
    """
    # Check if user is the tenant owner
    if tenant.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant owner privileges required"
        )
    
    return current_user


# -------------------------
# OPTIONAL DEPENDENCIES
# -------------------------
def get_optional_user(
    credentials: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise
    Useful for endpoints that work both with and without authentication
    """
    if not credentials:
        return None
    
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None