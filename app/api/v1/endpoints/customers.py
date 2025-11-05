from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import uuid4
from datetime import datetime
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.customer import Customer, ClientType, AccountManager
from app.models.invoice import Invoice
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse

router = APIRouter(prefix="/api/v1/customers", tags=["Customers"])


def _to_response(customer: Customer, client_type_name: str = "", account_manager_name: str = "") -> CustomerResponse:
    """Convert Customer model to response schema"""
    return CustomerResponse(
        id=str(customer.id),
        code=customer.code,
        name=customer.name,
        type=client_type_name,
        typeId=str(customer.client_type_id) if customer.client_type_id else "",
        address=customer.address or "",
        email=customer.email or "",
        whatsapp=customer.whatsapp or "",
        phone=customer.phone or "",
        contactPerson=customer.contact_person or "",
        gstNumber=customer.gst_number,
        panNumber=customer.pan_number,
        paymentTerms=customer.payment_terms,
        accountManager=account_manager_name,
        accountManagerId=str(customer.account_manager_id) if customer.account_manager_id else "",
        isActive=customer.is_active,
        createdAt=customer.created_at.isoformat() if customer.created_at else "",
        updatedAt=customer.updated_at.isoformat() if customer.updated_at else ""
    )


@router.get("", response_model=CustomerListResponse)
def list_customers(
    search: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    isActive: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    sortBy: str = Query(default="name"),
    sortOrder: str = Query(default="asc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get paginated list of customers with optional filtering and search"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Build query with filters - always filter by tenant_id
    query = db.query(
        Customer,
        ClientType.name.label('client_type_name'),
        AccountManager.name.label('account_manager_name')
    ).outerjoin(
        ClientType, Customer.client_type_id == ClientType.id
    ).outerjoin(
        AccountManager, Customer.account_manager_id == AccountManager.id
    ).filter(
        Customer.tenant_id == tenant_id
    )
    
    # Apply search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Customer.name.ilike(search_pattern),
                Customer.code.ilike(search_pattern),
                Customer.email.ilike(search_pattern)
            )
        )
    
    # Apply type filter
    if type:
        query = query.filter(Customer.client_type_id == type)
    
    # Apply isActive filter
    if isActive is not None:
        query = query.filter(Customer.is_active == isActive)
    
    # 7. Count total records for pagination
    total = query.count()
    
    # 5. Apply sorting
    if sortBy == "name":
        query = query.order_by(Customer.name.asc() if sortOrder == "asc" else Customer.name.desc())
    elif sortBy == "code":
        query = query.order_by(Customer.code.asc() if sortOrder == "asc" else Customer.code.desc())
    elif sortBy == "createdAt":
        query = query.order_by(Customer.created_at.asc() if sortOrder == "asc" else Customer.created_at.desc())
    
    # 6. Apply pagination (LIMIT, OFFSET)
    offset = (page - 1) * limit
    results = query.offset(offset).limit(limit).all()
    
    # 8. Calculate totalPages
    total_pages = (total + limit - 1) // limit
    
    # Convert to response
    data = [
        _to_response(customer, client_type_name or "", account_manager_name or "")
        for customer, client_type_name, account_manager_name in results
    ]
    
    # 9. Return data and pagination metadata
    return CustomerListResponse(
        data=data,
        pagination={
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
            "hasMore": page < total_pages
        }
    )


@router.get("/{id}", response_model=CustomerResponse)
def get_customer(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get single customer by ID with full details"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Query customer by ID AND tenant_id (ensure tenant isolation)
    # 3. JOIN with client_types and account_managers
    result = db.query(
        Customer,
        ClientType.name.label('client_type_name'),
        AccountManager.name.label('account_manager_name')
    ).outerjoin(
        ClientType, Customer.client_type_id == ClientType.id
    ).outerjoin(
        AccountManager, Customer.account_manager_id == AccountManager.id
    ).filter(
        Customer.id == id,
        Customer.tenant_id == tenant_id
    ).first()
    
    # 4. If not found, return 404
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    customer, client_type_name, account_manager_name = result
    
    # 5. Return customer
    return _to_response(customer, client_type_name or "", account_manager_name or "")


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new customer"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Validate all fields (handled by Pydantic)
    
    # 3. Check code uniqueness within tenant
    code_exists = db.query(Customer).filter(
        Customer.tenant_id == tenant_id,
        Customer.code == payload.code
    ).first()
    
    if code_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "Customer code already exists"}
        )
    
    # 4. Check email uniqueness within tenant
    email_exists = db.query(Customer).filter(
        Customer.tenant_id == tenant_id,
        Customer.email == payload.email
    ).first()
    
    if email_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"email": "Customer email already exists"}
        )
    
    # 5. Verify client_type_id exists and belongs to tenant
    client_type = db.query(ClientType).filter(
        ClientType.id == payload.type,
        ClientType.tenant_id == tenant_id
    ).first()
    
    if not client_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"type": "Invalid client type"}
        )
    
    # 6. Verify account_manager_id exists and belongs to tenant
    account_manager = db.query(AccountManager).filter(
        AccountManager.id == payload.accountManager,
        AccountManager.tenant_id == tenant_id
    ).first()
    
    if not account_manager:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"accountManager": "Invalid account manager"}
        )
    
    # 7-8. Validate GST and PAN formats (handled by Pydantic validators)
    
    # 9. Generate UUID for customer
    customer_id = uuid4()
    
    # 10. Set created_by = current user_id
    # 11. Insert customer record
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        code=payload.code,
        name=payload.name,
        client_type_id=payload.type,
        address=payload.address,
        email=payload.email,
        whatsapp=payload.whatsapp,
        phone=payload.phone,
        contact_person=payload.contactPerson,
        gst_number=payload.gstNumber,
        pan_number=payload.panNumber,
        payment_terms=payload.paymentTerms,
        account_manager_id=payload.accountManager,
        is_active=payload.isActive if payload.isActive is not None else True,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(customer)
    
    # 12. Increment tenant's customer count
    # TODO: Update tenants.current_customer_count
    
    db.commit()
    db.refresh(customer)
    
    # TODO: Create audit log entry
    # TODO: Check subscription limits (free tier: max 50 customers)
    
    # 13. Return created customer with joined data
    return _to_response(customer, client_type.name, account_manager.name)


@router.put("/{id}", response_model=CustomerResponse)
def update_customer(
    id: str,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update existing customer"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Verify customer exists and belongs to tenant
    customer = db.query(Customer).filter(
        Customer.id == id,
        Customer.tenant_id == tenant_id
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # 3. Validate all fields (handled by Pydantic)
    
    # 4. Check code uniqueness (excluding current customer)
    code_exists = db.query(Customer).filter(
        Customer.tenant_id == tenant_id,
        Customer.id != id,
        Customer.code == payload.code
    ).first()
    
    if code_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "Customer code already exists"}
        )
    
    # 5. Check email uniqueness (excluding current customer)
    email_exists = db.query(Customer).filter(
        Customer.tenant_id == tenant_id,
        Customer.id != id,
        Customer.email == payload.email
    ).first()
    
    if email_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"email": "Customer email already exists"}
        )
    
    # 6. Verify foreign key references
    client_type = db.query(ClientType).filter(
        ClientType.id == payload.type,
        ClientType.tenant_id == tenant_id
    ).first()
    
    if not client_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"type": "Invalid client type"}
        )
    
    account_manager = db.query(AccountManager).filter(
        AccountManager.id == payload.accountManager,
        AccountManager.tenant_id == tenant_id
    ).first()
    
    if not account_manager:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"accountManager": "Invalid account manager"}
        )
    
    # 7. Validate GST and PAN formats (handled by Pydantic validators)
    
    # 8. Update customer record
    customer.code = payload.code
    customer.name = payload.name
    customer.client_type_id = payload.type
    customer.address = payload.address
    customer.email = payload.email
    customer.whatsapp = payload.whatsapp
    customer.phone = payload.phone
    customer.contact_person = payload.contactPerson
    customer.gst_number = payload.gstNumber
    customer.pan_number = payload.panNumber
    customer.payment_terms = payload.paymentTerms
    customer.account_manager_id = payload.accountManager
    if payload.isActive is not None:
        customer.is_active = payload.isActive
    
    # 9. Set updated_at = NOW()
    customer.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(customer)
    
    # TODO: Create audit log entry with old and new values
    # TODO: May update related invoice customer names (denormalization)
    
    # 10. Return updated customer with joined data
    return _to_response(customer, client_type.name, account_manager.name)


@router.delete("/{id}")
def delete_customer(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete customer. Uses soft delete if has invoices, hard delete otherwise."""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Verify customer exists and belongs to tenant
    customer = db.query(Customer).filter(
        Customer.id == id,
        Customer.tenant_id == tenant_id
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # 3. Check if customer has any invoices
    invoice_count = db.query(func.count(Invoice.id)).filter(
        Invoice.customer_id == id,
        Invoice.tenant_id == tenant_id
    ).scalar()
    
    if invoice_count > 0:
        # Has invoices: Soft delete (set is_active = false, deleted_at = NOW())
        customer.is_active = False
        customer.updated_at = datetime.utcnow()
        db.commit()
        
        # TODO: Decrement tenant customer count
        # TODO: Create audit log entry
        
        # 5. Return success with deletion type
        return {
            "success": True,
            "message": "Customer deleted successfully",
            "type": "soft"
        }
    else:
        # No invoices: Hard delete (DELETE from table)
        db.delete(customer)
        db.commit()
        
        # TODO: Create audit log entry
        
        # 5. Return success with deletion type
        return {
            "success": True,
            "message": "Customer deleted successfully",
            "type": "hard"
        }
