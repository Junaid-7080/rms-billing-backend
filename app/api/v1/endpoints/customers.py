from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import uuid4
from datetime import datetime
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.company import Company
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse

router = APIRouter(prefix="/api/v1/customers", tags=["Customers"])


def _is_gst_applicable(company: Optional[Company]) -> bool:
    """Determine if GST fields should be captured for customers."""
    if not company:
        return True
    if not company.gst_applicable:
        return False
    if company.gst_compounding_company:
        return False
    return True


def _to_response(customer: Customer) -> CustomerResponse:
    """Convert Customer model to response schema"""
    return CustomerResponse(
        id=str(customer.id),
        code=customer.code,
        name=customer.name,
        addressLine1=customer.address_line1 or "",
        addressLine2=customer.address_line2 or "",
        addressLine3=customer.address_line3 or "",
        state=customer.state or "",
        country=customer.country or "",
        email=customer.email or "",
        whatsapp=customer.whatsapp or "",
        phone=customer.phone or "",
        contactPerson=customer.contact_person or "",
        customerNote=customer.customer_note or "",
        gstNumber=customer.gst_number,
        panNumber=customer.pan_number,
        gstExempted=customer.gst_exempted,
        gstExemptionReason=customer.gst_exemption_reason,
        paymentTerms=customer.payment_terms,
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
        _to_response(customer)
        for customer in results
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
    
    customer = result[0] if isinstance(result, tuple) else result
    
    # 5. Return customer
    return _to_response(customer)


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
    
    # 5. Determine GST applicability and enforce rules
    company = db.query(Company).filter(Company.tenant_id == tenant_id).first()
    gst_allowed = _is_gst_applicable(company)
    if not gst_allowed:
        if any([payload.gstNumber, payload.gstExempted, payload.gstExemptionReason]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GST fields are not applicable for this company"
            )
    
    gst_number = payload.gstNumber if gst_allowed else None
    gst_exempted = payload.gstExempted if gst_allowed else False
    gst_exemption_reason = payload.gstExemptionReason if gst_allowed else None
    
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
        client_type_id=None,
        address_line1=payload.addressLine1,
        address_line2=payload.addressLine2,
        address_line3=payload.addressLine3,
        state=payload.state,
        country=payload.country,
        email=payload.email,
        whatsapp=payload.whatsapp,
        phone=payload.phone,
        contact_person=payload.contactPerson,
        customer_note=payload.customerNote,
        gst_number=gst_number,
        pan_number=payload.panNumber,
        gst_exempted=gst_exempted,
        gst_exemption_reason=gst_exemption_reason,
        payment_terms=payload.paymentTerms,
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
    return _to_response(customer)

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
    
    # 3. Check code uniqueness (excluding current customer) - only if code is being updated
    if payload.code and payload.code != customer.code:
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
    
    # 4. Check email uniqueness (excluding current customer) - only if email is being updated
    if payload.email and payload.email != customer.email:
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
    
    # 5. Determine GST applicability
    company = db.query(Company).filter(Company.tenant_id == tenant_id).first()
    gst_allowed = _is_gst_applicable(company)
    if not gst_allowed:
        if any([
            payload.gstNumber,
            payload.gstExempted,
            payload.gstExemptionReason
        ]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GST fields are not applicable for this company"
            )
    
    # 7. Update customer record - only update fields that are provided
    if payload.code is not None:
        customer.code = payload.code
    if payload.name is not None:
        customer.name = payload.name
    if payload.addressLine1 is not None:
        customer.address_line1 = payload.addressLine1
    if payload.addressLine2 is not None:
        customer.address_line2 = payload.addressLine2
    if payload.addressLine3 is not None:
        customer.address_line3 = payload.addressLine3
    if payload.state is not None:
        customer.state = payload.state
    if payload.country is not None:
        customer.country = payload.country
    if payload.email is not None:
        customer.email = payload.email
    if payload.whatsapp is not None:
        customer.whatsapp = payload.whatsapp
    if payload.phone is not None:
        customer.phone = payload.phone
    if payload.contactPerson is not None:
        customer.contact_person = payload.contactPerson
    if payload.customerNote is not None:
        customer.customer_note = payload.customerNote
    if payload.gstNumber is not None and gst_allowed:
        customer.gst_number = payload.gstNumber
    if payload.panNumber is not None:
        customer.pan_number = payload.panNumber
    if payload.gstExempted is not None and gst_allowed:
        customer.gst_exempted = payload.gstExempted
        if not customer.gst_exempted:
            customer.gst_exemption_reason = None
    if payload.gstExemptionReason is not None and gst_allowed:
        customer.gst_exemption_reason = payload.gstExemptionReason
    if payload.paymentTerms is not None:
        customer.payment_terms = payload.paymentTerms
    if payload.isActive is not None:
        customer.is_active = payload.isActive
    
    if not gst_allowed:
        customer.gst_number = None
        customer.gst_exempted = False
        customer.gst_exemption_reason = None
    
    # 8. Set updated_at = NOW()
    customer.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(customer)
    
    # TODO: Create audit log entry with old and new values
    # TODO: May update related invoice customer names (denormalization)
    
    # 9. Return updated customer with joined data
    return _to_response(customer)


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
