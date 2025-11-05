from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import uuid4
from datetime import datetime
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.customer import ClientType, Customer
from app.schemas.client_type import ClientTypeCreate, ClientTypeUpdate, ClientTypeResponse, ClientTypeListResponse

router = APIRouter(prefix="/api/v1/client-types", tags=["Client Types"])


@router.get("", response_model=ClientTypeListResponse)
def list_client_types(
    search: Optional[str] = Query(default=None),
    isActive: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of all client types"""
    # Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # Query client_types WHERE tenant_id = ?
    query = db.query(ClientType).filter(ClientType.tenant_id == tenant_id)
    
    # Apply search filter if provided
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                ClientType.name.ilike(search_pattern),
                ClientType.code.ilike(search_pattern)
            )
        )
    
    # Apply isActive filter if provided
    if isActive is not None:
        query = query.filter(ClientType.is_active == isActive)
    
    # Count total
    total = query.count()
    
    # Order by name ASC
    query = query.order_by(ClientType.name.asc())
    
    # Apply pagination
    offset = (page - 1) * limit
    client_types = query.offset(offset).limit(limit).all()
    
    # Convert to response
    data = [
        ClientTypeResponse(
            id=str(ct.id),
            code=ct.code,
            name=ct.name,
            description=ct.description or "",
            paymentTerms=ct.payment_terms or 0,
            isActive=ct.is_active,
            createdAt=ct.created_at.isoformat() if ct.created_at else "",
            updatedAt=ct.updated_at.isoformat() if ct.updated_at else ""
        )
        for ct in client_types
    ]
    
    total_pages = (total + limit - 1) // limit
    
    return ClientTypeListResponse(
        data=data,
        pagination={
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
            "hasMore": page < total_pages
        }
    )


@router.post("", response_model=ClientTypeResponse, status_code=status.HTTP_201_CREATED)
def create_client_type(
    payload: ClientTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new client type"""
    # Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # Validate all fields (handled by Pydantic)
    
    # Check code uniqueness within tenant
    code_exists = db.query(ClientType).filter(
        ClientType.tenant_id == tenant_id,
        ClientType.code == payload.code
    ).first()
    
    if code_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client type code already exists"
        )
    
    # Check name uniqueness within tenant
    name_exists = db.query(ClientType).filter(
        ClientType.tenant_id == tenant_id,
        ClientType.name == payload.name
    ).first()
    
    if name_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client type name already exists"
        )
    
    # Generate UUID
    client_type_id = uuid4()
    
    # Insert client type
    client_type = ClientType(
        id=client_type_id,
        tenant_id=tenant_id,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        payment_terms=payload.paymentTerms,
        is_active=payload.isActive if payload.isActive is not None else True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(client_type)
    db.commit()
    db.refresh(client_type)
    
    # Return created client type
    return ClientTypeResponse(
        id=str(client_type.id),
        code=client_type.code,
        name=client_type.name,
        description=client_type.description,
        paymentTerms=client_type.payment_terms,
        isActive=client_type.is_active,
        createdAt=client_type.created_at.isoformat() if client_type.created_at else "",
        updatedAt=client_type.updated_at.isoformat() if client_type.updated_at else ""
    )


@router.put("/{id}", response_model=ClientTypeResponse)
def update_client_type(
    id: str,
    payload: ClientTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update client type"""
    # Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # Verify client type exists and belongs to tenant
    client_type = db.query(ClientType).filter(
        ClientType.id == id,
        ClientType.tenant_id == tenant_id
    ).first()
    
    if not client_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client type not found"
        )
    
    # Check code uniqueness (excluding self)
    code_exists = db.query(ClientType).filter(
        ClientType.tenant_id == tenant_id,
        ClientType.id != id,
        ClientType.code == payload.code
    ).first()
    
    if code_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client type code already exists"
        )
    
    # Check name uniqueness (excluding self)
    name_exists = db.query(ClientType).filter(
        ClientType.tenant_id == tenant_id,
        ClientType.id != id,
        ClientType.name == payload.name
    ).first()
    
    if name_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client type name already exists"
        )
    
    # Update fields
    client_type.code = payload.code
    client_type.name = payload.name
    client_type.description = payload.description
    client_type.payment_terms = payload.paymentTerms
    if payload.isActive is not None:
        client_type.is_active = payload.isActive
    client_type.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(client_type)
    
    return ClientTypeResponse(
        id=str(client_type.id),
        code=client_type.code,
        name=client_type.name,
        description=client_type.description,
        paymentTerms=client_type.payment_terms,
        isActive=client_type.is_active,
        createdAt=client_type.created_at.isoformat() if client_type.created_at else "",
        updatedAt=client_type.updated_at.isoformat() if client_type.updated_at else ""
    )


@router.delete("/{id}")
def delete_client_type(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete client type (only if not used by customers)"""
    # Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # Verify client type exists
    client_type = db.query(ClientType).filter(
        ClientType.id == id,
        ClientType.tenant_id == tenant_id
    ).first()
    
    if not client_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client type not found"
        )
    
    # 1. Check if type used by any customers
    usage_count = db.query(func.count(Customer.id)).filter(
        Customer.client_type_id == id,
        Customer.tenant_id == tenant_id
    ).scalar()
    
    # 2. If used, return 409
    if usage_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client type is used by customers"
        )
    
    # 3. If not used, DELETE
    db.delete(client_type)
    db.commit()
    
    return {"success": True, "message": "Client type deleted successfully"}
