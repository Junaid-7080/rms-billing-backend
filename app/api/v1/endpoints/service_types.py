from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import uuid4
from datetime import datetime
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.service import ServiceType
from app.models.invoice import InvoiceLineItem
from app.schemas.service_type import ServiceTypeCreate, ServiceTypeUpdate, ServiceTypeResponse, ServiceTypeListResponse

router = APIRouter(prefix="/api/v1/service-types", tags=["Service Types"])


@router.get("", response_model=ServiceTypeListResponse)
def list_service_types(
    search: Optional[str] = Query(default=None),
    isActive: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of all service types with optional filtering"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Query service_types WHERE tenant_id = ?
    query = db.query(ServiceType).filter(ServiceType.tenant_id == tenant_id)
    
    # 3. Apply search filter if provided
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                ServiceType.name.ilike(search_pattern),
                ServiceType.code.ilike(search_pattern)
            )
        )
    
    # 4. Apply isActive filter if provided
    if isActive is not None:
        query = query.filter(ServiceType.is_active == isActive)
    
    # Count total
    total = query.count()
    
    # Order by name
    query = query.order_by(ServiceType.name.asc())
    
    # 5. Apply pagination
    offset = (page - 1) * limit
    service_types = query.offset(offset).limit(limit).all()
    
    # Convert to response
    data = [
        ServiceTypeResponse(
            id=str(st.id),
            code=st.code,
            name=st.name,
            description=st.description,
            taxRate=float(st.tax_rate or 0),
            isActive=st.is_active,
            createdAt=st.created_at.isoformat() if st.created_at else "",
            updatedAt=st.updated_at.isoformat() if st.updated_at else ""
        )
        for st in service_types
    ]
    
    total_pages = (total + limit - 1) // limit
    
    # 6. Return results
    return ServiceTypeListResponse(
        data=data,
        pagination={
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
            "hasMore": page < total_pages
        }
    )


@router.post("", response_model=ServiceTypeResponse, status_code=status.HTTP_201_CREATED)
def create_service_type(
    payload: ServiceTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new service type"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Validate all fields (handled by Pydantic)
    
    # 3. Check code uniqueness within tenant
    code_exists = db.query(ServiceType).filter(
        ServiceType.tenant_id == tenant_id,
        ServiceType.code == payload.code
    ).first()
    
    if code_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service type code already exists"
        )
    
    # 4. Check name uniqueness within tenant
    name_exists = db.query(ServiceType).filter(
        ServiceType.tenant_id == tenant_id,
        ServiceType.name == payload.name
    ).first()
    
    if name_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service type name already exists"
        )
    
    # 5. Validate tax rate is between 0 and 100 (handled by Pydantic validator)
    
    # 6. Generate UUID
    service_type_id = uuid4()
    
    # 7. Insert service type
    service_type = ServiceType(
        id=service_type_id,
        tenant_id=tenant_id,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        tax_rate=payload.taxRate,
        is_active=payload.isActive if payload.isActive is not None else True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(service_type)
    db.commit()
    db.refresh(service_type)
    
    # 8. Return created service type
    return ServiceTypeResponse(
        id=str(service_type.id),
        code=service_type.code,
        name=service_type.name,
        description=service_type.description,
        taxRate=float(service_type.tax_rate),
        isActive=service_type.is_active,
        createdAt=service_type.created_at.isoformat() if service_type.created_at else "",
        updatedAt=service_type.updated_at.isoformat() if service_type.updated_at else ""
    )


@router.put("/{id}", response_model=ServiceTypeResponse)
def update_service_type(
    id: str,
    payload: ServiceTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update service type"""
    # Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # Verify service type exists and belongs to tenant
    service_type = db.query(ServiceType).filter(
        ServiceType.id == id,
        ServiceType.tenant_id == tenant_id
    ).first()
    
    if not service_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service type not found"
        )
    
    # Check code uniqueness (excluding self)
    code_exists = db.query(ServiceType).filter(
        ServiceType.tenant_id == tenant_id,
        ServiceType.id != id,
        ServiceType.code == payload.code
    ).first()
    
    if code_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service type code already exists"
        )
    
    # Check name uniqueness (excluding self)
    name_exists = db.query(ServiceType).filter(
        ServiceType.tenant_id == tenant_id,
        ServiceType.id != id,
        ServiceType.name == payload.name
    ).first()
    
    if name_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service type name already exists"
        )
    
    # Update fields
    service_type.code = payload.code
    service_type.name = payload.name
    service_type.description = payload.description
    service_type.tax_rate = payload.taxRate
    if payload.isActive is not None:
        service_type.is_active = payload.isActive
    service_type.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(service_type)
    
    return ServiceTypeResponse(
        id=str(service_type.id),
        code=service_type.code,
        name=service_type.name,
        description=service_type.description,
        taxRate=float(service_type.tax_rate),
        isActive=service_type.is_active,
        createdAt=service_type.created_at.isoformat() if service_type.created_at else "",
        updatedAt=service_type.updated_at.isoformat() if service_type.updated_at else ""
    )


@router.delete("/{id}")
def delete_service_type(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete service type (only if not used in invoices)"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Verify service type exists
    service_type = db.query(ServiceType).filter(
        ServiceType.id == id,
        ServiceType.tenant_id == tenant_id
    ).first()
    
    if not service_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service type not found"
        )
    
    # 3. Check if used in any invoice line items
    usage_count = db.query(func.count(InvoiceLineItem.id)).filter(
        InvoiceLineItem.service_type_id == id,
        InvoiceLineItem.tenant_id == tenant_id
    ).scalar()
    
    # 4. If used, return 409 Conflict
    if usage_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service type is used in invoices"
        )
    
    # 5. If not used, DELETE
    db.delete(service_type)
    db.commit()
    
    # 6. Return success
    return {"success": True, "message": "Service type deleted successfully"}
