from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.customer import AccountManager
from app.schemas.account_manager import AccountManagerResponse, AccountManagerListResponse

router = APIRouter(prefix="/api/v1/account-managers", tags=["Account Managers"])


@router.get("", response_model=AccountManagerListResponse)
def list_account_managers(
    isActive: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of all account managers"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Query account_managers WHERE tenant_id = ?
    query = db.query(AccountManager).filter(
        AccountManager.tenant_id == tenant_id
    )
    
    # 3. Filter by isActive if specified
    if isActive is not None:
        query = query.filter(AccountManager.is_active == isActive)
    
    # Order by name ASC
    query = query.order_by(AccountManager.name.asc())
    
    # Execute query
    account_managers = query.all()
    
    # Convert to response
    data = [
        AccountManagerResponse(
            id=str(am.id),
            name=am.name,
            email=am.email,
            isActive=am.is_active
        )
        for am in account_managers
    ]
    
    # 4. Return list (no pagination for simplicity)
    return AccountManagerListResponse(root=data)
