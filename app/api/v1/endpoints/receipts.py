from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import uuid4
from datetime import datetime, date
from typing import Optional
from decimal import Decimal

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.receipt import Receipt, ReceiptAllocation
from app.models.invoice import Invoice
from app.models.customer import Customer
from app.schemas.receipt import (
    ReceiptCreate,
    ReceiptResponse,
    ReceiptCreateResponse,
    ReceiptListResponse,
    ReceiptAllocationResponse
)

router = APIRouter(prefix="/api/v1/receipts", tags=["Receipts"])


def build_receipt_response(receipt, customer_name, allocations_with_invoices, include_invoices_updated=False):
    """Build receipt response with all details"""
    allocations = [
        ReceiptAllocationResponse(
            invoiceId=str(alloc.invoice_id),
            invoiceNumber=invoice_number,
            amountAllocated=float(alloc.allocated_amount)
        )
        for alloc, invoice_number in allocations_with_invoices
    ]
    
    total_allocated = sum(float(alloc.allocated_amount) for alloc, _ in allocations_with_invoices)
    unapplied_amount = float(receipt.amount) - total_allocated
    
    base_data = {
        "id": str(receipt.id),
        "receiptId": receipt.receipt_number,
        "receiptDate": receipt.receipt_date.isoformat(),
        "customerId": str(receipt.customer_id),
        "customerName": customer_name,
        "paymentMethod": receipt.payment_method,
        "amountReceived": float(receipt.amount),
        "allocations": allocations,
        "totalAllocated": round(total_allocated, 2),
        "unappliedAmount": round(unapplied_amount, 2),
        "notes": receipt.notes,
        "status": receipt.status or "Completed",
        "createdAt": receipt.created_at.isoformat() if receipt.created_at else ""
    }
    
    if include_invoices_updated:
        invoice_numbers = [invoice_number for _, invoice_number in allocations_with_invoices]
        return ReceiptCreateResponse(**base_data, invoicesUpdated=invoice_numbers)
    
    return ReceiptResponse(**base_data)


@router.get("", response_model=ReceiptListResponse)
def list_receipts(
    search: Optional[str] = Query(default=None),
    customerId: Optional[str] = Query(default=None),
    paymentMethod: Optional[str] = Query(default=None),
    dateFrom: Optional[date] = Query(default=None),
    dateTo: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of all payment receipts"""
    # Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # Query receipts with JOINs - JOIN with customers
    query = db.query(
        Receipt,
        Customer.name.label('customer_name')
    ).join(
        Customer, Receipt.customer_id == Customer.id
    ).filter(
        Receipt.tenant_id == tenant_id
    )
    
    # Apply filters
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Receipt.receipt_number.ilike(search_pattern),
                Customer.name.ilike(search_pattern)
            )
        )
    
    if customerId:
        query = query.filter(Receipt.customer_id == customerId)
    
    if paymentMethod:
        query = query.filter(Receipt.payment_method == paymentMethod.lower())
    
    if dateFrom:
        query = query.filter(Receipt.receipt_date >= dateFrom)
    
    if dateTo:
        query = query.filter(Receipt.receipt_date <= dateTo)
    
    # Count total
    total = query.count()
    
    # Order by receipt date DESC
    query = query.order_by(Receipt.receipt_date.desc())
    
    # Apply pagination
    offset = (page - 1) * limit
    results = query.offset(offset).limit(limit).all()
    
    # Build response with allocations
    data = []
    for receipt, customer_name in results:
        # JOIN with receipt_allocations and invoices for invoice numbers
        allocations_query = db.query(
            ReceiptAllocation,
            Invoice.invoice_number
        ).join(
            Invoice, ReceiptAllocation.invoice_id == Invoice.id
        ).filter(
            ReceiptAllocation.receipt_id == receipt.id
        ).all()
        
        data.append(build_receipt_response(receipt, customer_name, allocations_query))
    
    total_pages = (total + limit - 1) // limit
    
    return ReceiptListResponse(
        data=data,
        pagination={
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
            "hasMore": page < total_pages
        }
    )


@router.get("/{id}", response_model=ReceiptResponse)
def get_receipt(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get single receipt by ID"""
    tenant_id = current_user.tenant_id
    
    # Query receipt with customer
    result = db.query(
        Receipt,
        Customer.name.label('customer_name')
    ).join(
        Customer, Receipt.customer_id == Customer.id
    ).filter(
        Receipt.id == id,
        Receipt.tenant_id == tenant_id
    ).first()
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found"
        )
    
    receipt, customer_name = result
    
    # Get allocations with invoice numbers
    allocations_query = db.query(
        ReceiptAllocation,
        Invoice.invoice_number
    ).join(
        Invoice, ReceiptAllocation.invoice_id == Invoice.id
    ).filter(
        ReceiptAllocation.receipt_id == receipt.id
    ).all()
    
    return build_receipt_response(receipt, customer_name, allocations_query)


@router.post("", response_model=ReceiptCreateResponse, status_code=status.HTTP_201_CREATED)
def create_receipt(
    payload: ReceiptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Record a payment receipt and allocate to invoices"""
    # Get tenant_id and user_id from JWT
    tenant_id = current_user.tenant_id
    user_id = current_user.id
    
    # Verify customer exists
    customer = db.query(Customer).filter(
        Customer.id == payload.customerId,
        Customer.tenant_id == tenant_id
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer"
        )
    
    # Verify all invoices
    invoice_ids = [alloc.invoiceId for alloc in payload.allocations]
    invoices = db.query(Invoice).filter(
        Invoice.id.in_(invoice_ids),
        Invoice.customer_id == payload.customerId,
        Invoice.tenant_id == tenant_id
    ).all()
    
    # Check all invoices exist and belong to customer
    if len(invoices) != len(set(invoice_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more invoices not found or do not belong to this customer"
        )
    
    # Create invoice lookup map
    invoice_map = {str(inv.id): inv for inv in invoices}
    
    # Get existing allocations for these invoices
    existing_allocations = db.query(
        ReceiptAllocation.invoice_id,
        func.sum(ReceiptAllocation.allocated_amount).label('total_allocated')
    ).filter(
        ReceiptAllocation.invoice_id.in_(invoice_ids)
    ).group_by(ReceiptAllocation.invoice_id).all()
    
    existing_alloc_map = {str(inv_id): float(total) for inv_id, total in existing_allocations}
    
    # Validate allocations
    total_allocated = 0
    for alloc in payload.allocations:
        invoice = invoice_map[alloc.invoiceId]
        existing_paid = existing_alloc_map.get(alloc.invoiceId, 0)
        outstanding = float(invoice.total) - existing_paid
        
        # Check if invoice is already fully paid
        if outstanding <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invoice {invoice.invoice_number} is already fully paid"
            )
        
        # Check allocation doesn't exceed outstanding
        if alloc.amountAllocated > outstanding:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Allocation amount {alloc.amountAllocated} exceeds outstanding amount {outstanding} for invoice {invoice.invoice_number}"
            )
        
        total_allocated += alloc.amountAllocated
    
    # Check total allocations don't exceed amount received
    if total_allocated > payload.amountReceived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Total allocations ({total_allocated}) exceed amount received ({payload.amountReceived})"
        )
    
    # Check receipt ID uniqueness or auto-generate
    if payload.receiptId:
        existing = db.query(Receipt).filter(
            Receipt.tenant_id == tenant_id,
            Receipt.receipt_number == payload.receiptId
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Receipt ID already exists"
            )
        receipt_number = payload.receiptId
    else:
        # Auto-generate receipt number
        year = payload.receiptDate.year
        count = db.query(func.count(Receipt.id)).filter(
            Receipt.tenant_id == tenant_id
        ).scalar() + 1
        receipt_number = f"RCT-{year}-{count:04d}"
    
    # Calculate unapplied amount
    unapplied_amount = payload.amountReceived - total_allocated
    
    # Insert receipt record
    receipt_id = uuid4()
    receipt = Receipt(
        id=receipt_id,
        tenant_id=tenant_id,
        receipt_number=receipt_number,
        receipt_date=payload.receiptDate,
        customer_id=payload.customerId,
        payment_method=payload.paymentMethod,
        amount=payload.amountReceived,
        status="Completed",
        notes=payload.notes,
        created_by=user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(receipt)
    
    # Insert allocation records for each invoice
    invoices_updated = []
    for alloc in payload.allocations:
        allocation = ReceiptAllocation(
            id=uuid4(),
            tenant_id=tenant_id,
            receipt_id=receipt_id,
            invoice_id=alloc.invoiceId,
            allocated_amount=alloc.amountAllocated,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(allocation)
        
        # Update invoice updated_at timestamp
        # Note: Invoice status is now calculated dynamically based on receipt allocations
        # So we don't need to update payment_status field anymore
        invoice = invoice_map[alloc.invoiceId]
        invoice.updated_at = datetime.utcnow()
        invoices_updated.append(invoice.invoice_number)
    
    db.commit()
    db.refresh(receipt)
    
    # Get allocations with invoice numbers for response
    allocations_query = db.query(
        ReceiptAllocation,
        Invoice.invoice_number
    ).join(
        Invoice, ReceiptAllocation.invoice_id == Invoice.id
    ).filter(
        ReceiptAllocation.receipt_id == receipt.id
    ).all()
    
    # Return created receipt with invoices updated
    return build_receipt_response(receipt, customer.name, allocations_query, include_invoices_updated=True)