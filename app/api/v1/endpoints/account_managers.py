from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.customer import AccountManager
from app.schemas.account_manager import AccountManagerResponse, AccountManagerListResponse, AccountManagerCreateRequest

router = APIRouter(prefix="/api/v1/account-managers", tags=["Account Managers"])

# ------------------------------
# Create Account Manager
# ------------------------------
@router.post("", response_model=AccountManagerResponse)
def create_account_manager(
    request: AccountManagerCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new account manager for current tenant"""
    
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current user not associated with any tenant"
        )
    
    # Check if email already exists for this tenant
    existing = db.query(AccountManager).filter(
        AccountManager.email == request.email,
        AccountManager.tenant_id == tenant_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account manager with this email already exists"
        )
    
    manager = AccountManager(
        id=uuid.uuid4(),
        name=request.name,
        email=request.email,
        tenant_id=tenant_id,  # ✅ assign tenant_id
        is_active=request.isActive
    )
    db.add(manager)
    db.commit()
    db.refresh(manager)
    
    return AccountManagerResponse(
        id=str(manager.id),
        name=manager.name,
        email=manager.email,
        isActive=manager.is_active
    )

# ------------------------------
# List Account Managers
# ------------------------------
@router.get("", response_model=AccountManagerListResponse)
def list_account_managers(
    isActive: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of all account managers for current tenant"""
    
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current user not associated with any tenant"
        )

    query = db.query(AccountManager).filter(AccountManager.tenant_id == tenant_id)

    if isActive is not None:
        query = query.filter(AccountManager.is_active == isActive)

    query = query.order_by(AccountManager.name.asc())
    managers = query.all()

    data = [
        AccountManagerResponse(
            id=str(m.id),
            name=m.name,
            email=m.email,
            isActive=m.is_active
        )
        for m in managers
    ]
    
    return AccountManagerListResponse(root=data)
