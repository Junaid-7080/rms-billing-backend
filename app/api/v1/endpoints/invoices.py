from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from uuid import uuid4
from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal
import io

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.customer import Customer
from app.models.service import ServiceType
from app.models.receipt import ReceiptAllocation
from app.models.credit_note import CreditNote
from app.models.company import Company
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceListResponse,
    InvoiceLineItemResponse,
    EmailInvoiceRequest,
    EmailInvoiceResponse
)
from app.services.pdf import generate_invoice_pdf
from app.services.email import send_invoice_email as send_email

router = APIRouter(prefix="/api/v1/invoices", tags=["Invoices"])


def calculate_line_item_amounts(line_item_data):
    """Calculate amounts for a line item"""
    amount = float(line_item_data.quantity) * float(line_item_data.rate)
    tax_amount = amount * (float(line_item_data.taxRate) / 100)
    total = amount + tax_amount
    
    return {
        'amount': round(amount, 2),
        'tax_amount': round(tax_amount, 2),
        'total': round(total, 2)
    }


def calculate_invoice_status(invoice, db: Session):
    """Calculate invoice status based on receipts and due date"""
    # Check if invoice is fully paid by checking receipt allocations
    # NOTE: Change 'allocated_amount' to your actual column name if different
    total_allocated = db.query(func.sum(ReceiptAllocation.allocated_amount)).filter(
        ReceiptAllocation.invoice_id == invoice.id
    ).scalar() or 0
    
    if total_allocated >= invoice.total:
        return 'Paid'
    elif invoice.due_date < date.today():
        return 'Overdue'
    else:
        return 'Pending'


def build_invoice_response(invoice, customer, line_items_with_service, db: Session):
    """Build invoice response with all details"""
    line_items = [
        InvoiceLineItemResponse(
            id=str(li.id),
            serviceType=str(li.service_type_id) if li.service_type_id else "",
            serviceTypeName=service_name or "",
            description=li.description,
            quantity=float(li.quantity),
            rate=float(li.rate),
            amount=float(li.amount),
            taxRate=float(li.tax_rate),
            taxAmount=float(li.tax_amount),
            total=float(li.total)
        )
        for li, service_name in line_items_with_service
    ]
    
    return InvoiceResponse(
        id=str(invoice.id),
        invoiceNumber=invoice.invoice_number,
        invoiceDate=invoice.invoice_date.isoformat(),
        customerId=str(invoice.customer_id),
        customerName=customer.name,
        customerGst=customer.gst_number,
        dueDate=invoice.due_date.isoformat(),
        referenceNumber=invoice.reference_number,
        lineItems=line_items,
        subtotal=float(invoice.subtotal),
        taxTotal=float(invoice.tax_total),
        total=float(invoice.total),
        status=calculate_invoice_status(invoice, db),
        notes=invoice.notes,
        createdAt=invoice.created_at.isoformat() if invoice.created_at else "",
        updatedAt=invoice.updated_at.isoformat() if invoice.updated_at else ""
    )


@router.get("", response_model=InvoiceListResponse)
def list_invoices(
    search: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    customerId: Optional[str] = Query(default=None),
    dateFrom: Optional[date] = Query(default=None),
    dateTo: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    sortBy: str = Query(default="invoiceDate"),
    sortOrder: str = Query(default="desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get paginated list of invoices with filtering and search"""
    # Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # Build query with filters
    # JOIN with customers for customer details
    query = db.query(
        Invoice,
        Customer.name.label('customer_name'),
        Customer.gst_number.label('customer_gst')
    ).join(
        Customer, Invoice.customer_id == Customer.id
    ).filter(
        Invoice.tenant_id == tenant_id
    )
    
    # Apply search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Invoice.invoice_number.ilike(search_pattern),
                Customer.name.ilike(search_pattern)
            )
        )
    
    # Apply status filter (calculated dynamically based on receipts)
    if status:
        today = date.today()
        if status == "Paid":
            # Subquery to get invoices that are fully paid
            paid_invoice_ids = db.query(ReceiptAllocation.invoice_id).group_by(
                ReceiptAllocation.invoice_id
            ).having(
                func.sum(ReceiptAllocation.amount) >= Invoice.total
            ).subquery()
            
            query = query.filter(Invoice.id.in_(paid_invoice_ids))
            
        elif status == "Overdue":
            # Invoices that are not fully paid and past due date
            paid_invoice_ids = db.query(ReceiptAllocation.invoice_id).group_by(
                ReceiptAllocation.invoice_id
            ).having(
                func.sum(ReceiptAllocation.amount) >= Invoice.total
            ).subquery()
            
            query = query.filter(
                and_(
                    ~Invoice.id.in_(paid_invoice_ids),
                    Invoice.due_date < today
                )
            )
            
        elif status == "Pending":
            # Invoices that are not fully paid and not overdue
            paid_invoice_ids = db.query(ReceiptAllocation.invoice_id).group_by(
                ReceiptAllocation.invoice_id
            ).having(
                func.sum(ReceiptAllocation.amount) >= Invoice.total
            ).subquery()
            
            query = query.filter(
                and_(
                    ~Invoice.id.in_(paid_invoice_ids),
                    Invoice.due_date >= today
                )
            )
    
    # Apply customer filter
    if customerId:
        query = query.filter(Invoice.customer_id == customerId)
    
    # Apply date filters
    if dateFrom:
        query = query.filter(Invoice.invoice_date >= dateFrom)
    if dateTo:
        query = query.filter(Invoice.invoice_date <= dateTo)
    
    # Count total
    total = query.count()
    
    # Apply sorting
    if sortBy == "invoiceNumber":
        query = query.order_by(
            Invoice.invoice_number.asc() if sortOrder == "asc" 
            else Invoice.invoice_number.desc()
        )
    elif sortBy == "invoiceDate":
        query = query.order_by(
            Invoice.invoice_date.asc() if sortOrder == "asc" 
            else Invoice.invoice_date.desc()
        )
    elif sortBy == "total":
        query = query.order_by(
            Invoice.total.asc() if sortOrder == "asc" 
            else Invoice.total.desc()
        )
    
    # Apply pagination
    offset = (page - 1) * limit
    results = query.offset(offset).limit(limit).all()
    
    # Return nested structure with line items
    data = []
    for invoice, customer_name, customer_gst in results:
        # JOIN with invoice_line_items for line items
        # JOIN with service_types for service names
        line_items_query = db.query(
            InvoiceLineItem,
            ServiceType.name.label('service_name')
        ).outerjoin(
            ServiceType, InvoiceLineItem.service_type_id == ServiceType.id
        ).filter(
            InvoiceLineItem.invoice_id == invoice.id
        ).order_by(InvoiceLineItem.created_at.asc()).all()
        
        # Build customer object
        customer = type('Customer', (), {
            'name': customer_name,
            'gst_number': customer_gst
        })()
        
        data.append(build_invoice_response(invoice, customer, line_items_query, db))
    
    total_pages = (total + limit - 1) // limit
    
    return InvoiceListResponse(
        data=data,
        pagination={
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
            "hasMore": page < total_pages
        }
    )


@router.get("/{id}", response_model=InvoiceResponse)
def get_invoice(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get single invoice by ID with full details including nested line items"""
    # Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # Query invoice by ID AND tenant_id
    # JOIN with customer
    result = db.query(
        Invoice,
        Customer
    ).join(
        Customer, Invoice.customer_id == Customer.id
    ).filter(
        Invoice.id == id,
        Invoice.tenant_id == tenant_id
    ).first()
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    invoice, customer = result
    
    # Fetch all line items with service type names
    line_items_query = db.query(
        InvoiceLineItem,
        ServiceType.name.label('service_name')
    ).outerjoin(
        ServiceType, InvoiceLineItem.service_type_id == ServiceType.id
    ).filter(
        InvoiceLineItem.invoice_id == invoice.id
    ).order_by(InvoiceLineItem.created_at.asc()).all()
    
    # Return complete invoice object
    return build_invoice_response(invoice, customer, line_items_query, db)


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new invoice with line items"""
    # Get tenant_id and user_id from JWT
    tenant_id = current_user.tenant_id
    user_id = current_user.id
    
    # Validate all fields (handled by Pydantic)
    
    # Verify customer exists and belongs to tenant
    customer = db.query(Customer).filter(
        Customer.id == payload.customerId,
        Customer.tenant_id == tenant_id
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer"
        )
    
    # Verify all service types exist and belong to tenant
    service_type_ids = [li.serviceType for li in payload.lineItems]
    service_types = db.query(ServiceType).filter(
        ServiceType.id.in_(service_type_ids),
        ServiceType.tenant_id == tenant_id
    ).all()
    
    if len(service_types) != len(set(service_type_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid service type"
        )
    
    # Check invoice number uniqueness or auto-generate
    if payload.invoiceNumber:
        existing = db.query(Invoice).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.invoice_number == payload.invoiceNumber
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invoice number already exists"
            )
        invoice_number = payload.invoiceNumber
    else:
        # Auto-generate invoice number
        year = payload.invoiceDate.year
        count = db.query(func.count(Invoice.id)).filter(
            Invoice.tenant_id == tenant_id
        ).scalar() + 1
        invoice_number = f"INV-{year}-{count:04d}"
    
    # Calculate line item amounts
    line_items_data = []
    for li in payload.lineItems:
        amounts = calculate_line_item_amounts(li)
        line_items_data.append({
            'data': li,
            'amounts': amounts
        })
    
    # Calculate invoice totals
    subtotal = sum(li['amounts']['amount'] for li in line_items_data)
    tax_total = sum(li['amounts']['tax_amount'] for li in line_items_data)
    total = subtotal + tax_total
    
    # Insert invoice record (NO payment_status field)
    invoice_id = uuid4()
    invoice = Invoice(
        id=invoice_id,
        tenant_id=tenant_id,
        invoice_number=invoice_number,
        invoice_date=payload.invoiceDate,
        customer_id=payload.customerId,
        due_date=payload.dueDate,
        reference_number=payload.referenceNumber,
        subtotal=subtotal,
        tax_total=tax_total,
        total=total,
        notes=payload.notes,
        created_by=user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(invoice)
    
    # Insert line items
    for li_data in line_items_data:
        line_item = InvoiceLineItem(
            id=uuid4(),
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            service_type_id=li_data['data'].serviceType,
            description=li_data['data'].description,
            quantity=li_data['data'].quantity,
            rate=li_data['data'].rate,
            amount=li_data['amounts']['amount'],
            tax_rate=li_data['data'].taxRate,
            tax_amount=li_data['amounts']['tax_amount'],
            total=li_data['amounts']['total'],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(line_item)
    
    db.commit()
    db.refresh(invoice)
    
    # Fetch line items with service names for response
    line_items_query = db.query(
        InvoiceLineItem,
        ServiceType.name.label('service_name')
    ).outerjoin(
        ServiceType, InvoiceLineItem.service_type_id == ServiceType.id
    ).filter(
        InvoiceLineItem.invoice_id == invoice.id
    ).order_by(InvoiceLineItem.created_at.asc()).all()
    
    return build_invoice_response(invoice, customer, line_items_query, db)


@router.put("/{id}", response_model=InvoiceResponse)
def update_invoice(
    id: str,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update existing invoice (only if not fully paid)"""
    # Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # Verify invoice exists and belongs to tenant
    invoice = db.query(Invoice).filter(
        Invoice.id == id,
        Invoice.tenant_id == tenant_id
    ).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Check if invoice is fully paid (by checking receipts)
    total_allocated = db.query(func.sum(ReceiptAllocation.amount)).filter(
        ReceiptAllocation.invoice_id == id
    ).scalar() or 0
    
    if total_allocated >= invoice.total:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit paid invoices"
        )
    
    # Check for any receipt allocations
    receipt_count = db.query(func.count(ReceiptAllocation.id)).filter(
        ReceiptAllocation.invoice_id == id
    ).scalar()
    
    if receipt_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit invoices with receipts allocated"
        )
    
    # Validate customer
    customer = db.query(Customer).filter(
        Customer.id == payload.customerId,
        Customer.tenant_id == tenant_id
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer"
        )
    
    # Verify service types
    service_type_ids = [li.serviceType for li in payload.lineItems]
    service_types = db.query(ServiceType).filter(
        ServiceType.id.in_(service_type_ids),
        ServiceType.tenant_id == tenant_id
    ).all()
    
    if len(service_types) != len(set(service_type_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid service type"
        )
    
    # Check invoice number uniqueness (excluding self)
    if payload.invoiceNumber and payload.invoiceNumber != invoice.invoice_number:
        existing = db.query(Invoice).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.id != id,
            Invoice.invoice_number == payload.invoiceNumber
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invoice number already exists"
            )
    
    # Delete existing line items
    db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == id
    ).delete()
    
    # Insert new line items with recalculated amounts
    line_items_data = []
    for li in payload.lineItems:
        amounts = calculate_line_item_amounts(li)
        line_items_data.append({
            'data': li,
            'amounts': amounts
        })
    
    # Recalculate invoice totals
    subtotal = sum(li['amounts']['amount'] for li in line_items_data)
    tax_total = sum(li['amounts']['tax_amount'] for li in line_items_data)
    total = subtotal + tax_total
    
    # Insert new line items
    for li_data in line_items_data:
        line_item = InvoiceLineItem(
            id=uuid4(),
            tenant_id=tenant_id,
            invoice_id=id,
            service_type_id=li_data['data'].serviceType,
            description=li_data['data'].description,
            quantity=li_data['data'].quantity,
            rate=li_data['data'].rate,
            amount=li_data['amounts']['amount'],
            tax_rate=li_data['data'].taxRate,
            tax_amount=li_data['amounts']['tax_amount'],
            total=li_data['amounts']['total'],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(line_item)
    
    # Update invoice record (NO payment_status)
    invoice.invoice_number = payload.invoiceNumber or invoice.invoice_number
    invoice.invoice_date = payload.invoiceDate
    invoice.customer_id = payload.customerId
    invoice.due_date = payload.dueDate
    invoice.reference_number = payload.referenceNumber
    invoice.subtotal = subtotal
    invoice.tax_total = tax_total
    invoice.total = total
    invoice.notes = payload.notes
    invoice.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(invoice)
    
    # Fetch line items with service names for response
    line_items_query = db.query(
        InvoiceLineItem,
        ServiceType.name.label('service_name')
    ).outerjoin(
        ServiceType, InvoiceLineItem.service_type_id == ServiceType.id
    ).filter(
        InvoiceLineItem.invoice_id == invoice.id
    ).order_by(InvoiceLineItem.created_at.asc()).all()
    
    return build_invoice_response(invoice, customer, line_items_query, db)


@router.delete("/{id}")
def delete_invoice(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete invoice (only if no payments received)"""
    # Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # Verify invoice exists
    invoice = db.query(Invoice).filter(
        Invoice.id == id,
        Invoice.tenant_id == tenant_id
    ).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Check for receipt allocations
    receipt_count = db.query(func.count(ReceiptAllocation.id)).filter(
        ReceiptAllocation.invoice_id == id
    ).scalar()
    
    if receipt_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete invoices with receipts"
        )
    
    # Check for credit notes
    credit_note_count = db.query(func.count(CreditNote.id)).filter(
        CreditNote.invoice_id == id
    ).scalar()
    
    if credit_note_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete invoices with credit notes"
        )
    
    # Delete line items first
    db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == id
    ).delete()
    
    # Delete invoice
    db.delete(invoice)
    
    db.commit()
    
    return {
        "success": True,
        "message": "Invoice deleted successfully"
    }


@router.get("/{id}/pdf")
def get_invoice_pdf(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate and download invoice PDF"""
    # Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # Fetch invoice with all details
    result = db.query(
        Invoice,
        Customer
    ).join(
        Customer, Invoice.customer_id == Customer.id
    ).filter(
        Invoice.id == id,
        Invoice.tenant_id == tenant_id
    ).first()
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    invoice, customer = result
    
    # Get company data
    company = db.query(Company).filter(Company.tenant_id == tenant_id).first()
    
    # Get line items
    line_items = db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == id
    ).all()
    
    # Prepare invoice data
    invoice_data = {
        "invoiceNumber": invoice.invoice_number,
        "invoiceDate": invoice.invoice_date.isoformat(),
        "dueDate": invoice.due_date.isoformat(),
        "customerName": customer.name,
        "customerEmail": customer.email or "",
        "customerPhone": customer.phone or "",
        "lineItems": [
            {
                "description": li.description,
                "quantity": float(li.quantity),
                "rate": float(li.rate),
                "taxRate": float(li.tax_rate),
                "amount": float(li.amount),
                "taxAmount": float(li.tax_amount),
                "total": float(li.total)
            }
            for li in line_items
        ],
        "subtotal": float(invoice.subtotal),
        "taxTotal": float(invoice.tax_total),
        "total": float(invoice.total),
        "notes": invoice.notes or ""
    }
    
    company_data = {
        "name": company.name if company else "Company Name",
        "address": company.address if company else "",
        "taxId": company.tax_id if company else ""
    }
    
    # Generate PDF
    pdf_content = generate_invoice_pdf(invoice_data, company_data)
    
    # Return PDF as download
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Invoice_{invoice.invoice_number}.pdf"
        }
    )


@router.post("/{id}/send-email", response_model=EmailInvoiceResponse)
def send_invoice_email(
    id: str,
    payload: EmailInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Email invoice PDF to customer"""
    # Verify invoice exists
    tenant_id = current_user.tenant_id
    
    result = db.query(
        Invoice,
        Customer
    ).join(
        Customer, Invoice.customer_id == Customer.id
    ).filter(
        Invoice.id == id,
        Invoice.tenant_id == tenant_id
    ).first()
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    invoice, customer = result
    
    # Get company data
    company = db.query(Company).filter(Company.tenant_id == tenant_id).first()
    
    # Get line items
    line_items = db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == id
    ).all()
    
    # Prepare invoice data
    invoice_data = {
        "invoiceNumber": invoice.invoice_number,
        "invoiceDate": invoice.invoice_date.isoformat(),
        "dueDate": invoice.due_date.isoformat(),
        "customerName": customer.name,
        "customerEmail": customer.email or "",
        "customerPhone": customer.phone or "",
        "lineItems": [
            {
                "description": li.description,
                "quantity": float(li.quantity),
                "rate": float(li.rate),
                "taxRate": float(li.tax_rate),
                "amount": float(li.amount),
                "taxAmount": float(li.tax_amount),
                "total": float(li.total)
            }
            for li in line_items
        ],
        "subtotal": float(invoice.subtotal),
        "taxTotal": float(invoice.tax_total),
        "total": float(invoice.total),
        "notes": invoice.notes or ""
    }
    
    company_data = {
        "name": company.name if company else "Company Name",
        "address": company.address if company else "",
        "taxId": company.tax_id if company else ""
    }
    
    # Generate PDF
    pdf_content = generate_invoice_pdf(invoice_data, company_data)
    
    # Send email with PDF attachment
    success = send_email(
        to_email=payload.recipientEmail,
        invoice_number=invoice.invoice_number,
        pdf_content=pdf_content
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send email. Please check SMTP configuration."
        )
    
    # Return success response
    return EmailInvoiceResponse(
        success=True,
        message=f"Invoice sent to {payload.recipientEmail}",
        sentTo=payload.recipientEmail,
        sentAt=datetime.utcnow().isoformat()
    )