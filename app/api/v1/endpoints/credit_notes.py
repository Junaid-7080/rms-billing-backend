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
from app.models.credit_note import CreditNote
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.schemas.credit_note import (
    CreditNoteCreate,
    CreditNoteResponse,
    CreditNoteListResponse
)

router = APIRouter(prefix="/api/v1/credit-notes", tags=["Credit Notes"])


def build_credit_note_response(credit_note, customer_name, invoice_number=None):
    """Build credit note response"""
    return CreditNoteResponse(
        id=str(credit_note.id),
        creditNoteId=credit_note.credit_note_number,
        creditNoteDate=credit_note.credit_note_date.isoformat(),
        customerId=str(credit_note.customer_id),
        customerName=customer_name,
        invoiceId=str(credit_note.invoice_id) if credit_note.invoice_id else None,
        invoiceNumber=invoice_number,
        reason=credit_note.reason,
        amount=float(credit_note.amount),
        gstRate=float(credit_note.gst_rate),
        gstAmount=float(credit_note.gst_amount),
        totalCredit=float(credit_note.total_credit),
        status=credit_note.status or "Issued",
        notes=credit_note.notes,
        createdAt=credit_note.created_at.isoformat() if credit_note.created_at else ""
    )


@router.get("", response_model=CreditNoteListResponse)
def list_credit_notes(
    search: Optional[str] = Query(default=None),
    customerId: Optional[str] = Query(default=None),
    invoiceId: Optional[str] = Query(default=None),
    reason: Optional[str] = Query(default=None),
    dateFrom: Optional[date] = Query(default=None),
    dateTo: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of all credit notes"""
    # 1. Query credit_notes with JOINs
    tenant_id = current_user.tenant_id
    
    # 2. JOIN with customers and invoices
    query = db.query(
        CreditNote,
        Customer.name.label('customer_name'),
        Invoice.invoice_number.label('invoice_number')
    ).join(
        Customer, CreditNote.customer_id == Customer.id
    ).outerjoin(
        Invoice, CreditNote.invoice_id == Invoice.id
    ).filter(
        CreditNote.tenant_id == tenant_id
    )
    
    # 3. Apply filters
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                CreditNote.credit_note_number.ilike(search_pattern),
                Customer.name.ilike(search_pattern)
            )
        )
    
    if customerId:
        query = query.filter(CreditNote.customer_id == customerId)
    
    if invoiceId:
        query = query.filter(CreditNote.invoice_id == invoiceId)
    
    if reason:
        query = query.filter(CreditNote.reason.ilike(f"%{reason}%"))
    
    if dateFrom:
        query = query.filter(CreditNote.credit_note_date >= dateFrom)
    
    if dateTo:
        query = query.filter(CreditNote.credit_note_date <= dateTo)
    
    # Count total
    total = query.count()
    
    # Order by credit note date DESC
    query = query.order_by(CreditNote.credit_note_date.desc())
    
    # 4. Apply pagination
    offset = (page - 1) * limit
    results = query.offset(offset).limit(limit).all()
    
    # Build response
    data = [
        build_credit_note_response(cn, customer_name, invoice_number)
        for cn, customer_name, invoice_number in results
    ]
    
    total_pages = (total + limit - 1) // limit
    
    return CreditNoteListResponse(
        data=data,
        pagination={
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
            "hasMore": page < total_pages
        }
    )


@router.get("/{id}", response_model=CreditNoteResponse)
def get_credit_note(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get single credit note by ID"""
    tenant_id = current_user.tenant_id
    
    # Query credit note with customer and invoice
    result = db.query(
        CreditNote,
        Customer.name.label('customer_name'),
        Invoice.invoice_number.label('invoice_number')
    ).join(
        Customer, CreditNote.customer_id == Customer.id
    ).outerjoin(
        Invoice, CreditNote.invoice_id == Invoice.id
    ).filter(
        CreditNote.id == id,
        CreditNote.tenant_id == tenant_id
    ).first()
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credit note not found"
        )
    
    credit_note, customer_name, invoice_number = result
    
    return build_credit_note_response(credit_note, customer_name, invoice_number)


@router.post("", response_model=CreditNoteResponse, status_code=status.HTTP_201_CREATED)
def create_credit_note(
    payload: CreditNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Issue a credit note (refund/adjustment)"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    user_id = current_user.id
    
    # 2. Validate all fields (handled by Pydantic)
    
    # 3. Verify customer exists
    customer = db.query(Customer).filter(
        Customer.id == payload.customerId,
        Customer.tenant_id == tenant_id
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer"
        )
    
    invoice = None
    invoice_number = None
    
    # 4. If invoice provided, verify it
    if payload.invoiceId:
        invoice = db.query(Invoice).filter(
            Invoice.id == payload.invoiceId,
            Invoice.customer_id == payload.customerId,
            Invoice.tenant_id == tenant_id
        ).first()
        
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid invoice or invoice does not belong to this customer"
            )
        
        invoice_number = invoice.invoice_number
        
        # Check existing credits for this invoice
        existing_credits = db.query(
            func.sum(CreditNote.total_credit)
        ).filter(
            CreditNote.invoice_id == payload.invoiceId,
            CreditNote.status != 'Cancelled'
        ).scalar() or Decimal('0')
        
        # Calculate GST amount and total credit for validation - FIXED: Using Decimal
        gst_amount = Decimal(str(payload.amount)) * (Decimal(str(payload.gstRate)) / Decimal('100'))
        total_credit = Decimal(str(payload.amount)) + gst_amount
        
        # Verify total credits don't exceed invoice amount - FIXED: All Decimal types
        if existing_credits + total_credit > Decimal(str(invoice.total)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Total credits ({existing_credits + total_credit}) would exceed invoice total ({invoice.total})"
            )
    
    # 5. Check credit note ID uniqueness or auto-generate
    if payload.creditNoteId:
        existing = db.query(CreditNote).filter(
            CreditNote.tenant_id == tenant_id,
            CreditNote.credit_note_number == payload.creditNoteId
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Credit note ID already exists"
            )
        credit_note_number = payload.creditNoteId
    else:
        # Auto-generate credit note number
        year = payload.creditNoteDate.year
        count = db.query(func.count(CreditNote.id)).filter(
            CreditNote.tenant_id == tenant_id
        ).scalar() + 1
        credit_note_number = f"CN-{year}-{count:04d}"
    
    # 6. Calculate GST amount - Using Decimal
    gst_amount = Decimal(str(payload.amount)) * (Decimal(str(payload.gstRate)) / Decimal('100'))
    
    # 7. Calculate total credit - Using Decimal
    total_credit = Decimal(str(payload.amount)) + gst_amount
    
    # 8. Insert credit note record
    credit_note_id = uuid4()
    credit_note = CreditNote(
        id=credit_note_id,
        tenant_id=tenant_id,
        credit_note_number=credit_note_number,
        credit_note_date=payload.creditNoteDate,
        customer_id=payload.customerId,
        invoice_id=payload.invoiceId,
        reason=payload.reason,
        amount=payload.amount,
        gst_rate=payload.gstRate,
        gst_amount=gst_amount,
        total_credit=total_credit,
        status="Issued",
        notes=payload.notes,
        created_by=user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(credit_note)
    
    # 10. May create accounting entry (TODO)
    
    db.commit()
    db.refresh(credit_note)
    
    # 11. Return created credit note
    return build_credit_note_response(credit_note, customer.name, invoice_number)