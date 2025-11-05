from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
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
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceListResponse,
    InvoiceLineItemResponse,
    EmailInvoiceRequest,
    EmailInvoiceResponse
)

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


def calculate_invoice_status(invoice):
    """Calculate invoice status based on due date and payment status"""
    if invoice.payment_status == 'paid':
        return 'Paid'
    elif invoice.due_date < date.today():
        return 'Overdue'
    else:
        return 'Pending'


def build_invoice_response(invoice, customer, line_items_with_service):
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
        status=calculate_invoice_status(invoice),
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
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Build query with filters
    # 3. JOIN with customers for customer details
    query = db.query(
        Invoice,
        Customer.name.label('customer_name'),
        Customer.gst_number.label('customer_gst')
    ).join(
        Customer, Invoice.customer_id == Customer.id
    ).filter(
        Invoice.tenant_id == tenant_id
    )
    
    # 7. Apply search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Invoice.invoice_number.ilike(search_pattern),
                Customer.name.ilike(search_pattern)
            )
        )
    
    # Apply status filter (calculated dynamically)
    if status:
        today = date.today()
        if status == "Paid":
            query = query.filter(Invoice.payment_status == 'paid')
        elif status == "Overdue":
            query = query.filter(
                and_(
                    Invoice.payment_status != 'paid',
                    Invoice.due_date < today
                )
            )
        elif status == "Pending":
            query = query.filter(
                and_(
                    Invoice.payment_status != 'paid',
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
    
    # 8. Apply sorting
    if sortBy == "invoiceNumber":
        query = query.order_by(Invoice.invoice_number.asc() if sortOrder == "asc" else Invoice.invoice_number.desc())
    elif sortBy == "invoiceDate":
        query = query.order_by(Invoice.invoice_date.asc() if sortOrder == "asc" else Invoice.invoice_date.desc())
    elif sortBy == "total":
        query = query.order_by(Invoice.total.asc() if sortOrder == "asc" else Invoice.total.desc())
    
    # Apply pagination
    offset = (page - 1) * limit
    results = query.offset(offset).limit(limit).all()
    
    # 9. Return nested structure with line items
    data = []
    for invoice, customer_name, customer_gst in results:
        # 4. JOIN with invoice_line_items for line items
        # 5. JOIN with service_types for service names
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
        
        data.append(build_invoice_response(invoice, customer, line_items_query))
    
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
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Query invoice by ID AND tenant_id
    # 3. JOIN with customer
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
    
    # 4. Fetch all line items with service type names
    line_items_query = db.query(
        InvoiceLineItem,
        ServiceType.name.label('service_name')
    ).outerjoin(
        ServiceType, InvoiceLineItem.service_type_id == ServiceType.id
    ).filter(
        InvoiceLineItem.invoice_id == invoice.id
    ).order_by(InvoiceLineItem.created_at.asc()).all()
    
    # 5. Return complete invoice object
    return build_invoice_response(invoice, customer, line_items_query)


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new invoice with line items"""
    # 1. Get tenant_id and user_id from JWT
    tenant_id = current_user.tenant_id
    user_id = current_user.id
    
    # 2. Check subscription limits (TODO: implement properly)
    # For now, skip this check
    
    # 3. Validate all fields (handled by Pydantic)
    
    # 4. Verify customer exists and belongs to tenant
    customer = db.query(Customer).filter(
        Customer.id == payload.customerId,
        Customer.tenant_id == tenant_id
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer"
        )
    
    # 5. Verify all service types exist and belong to tenant
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
    
    # 6. Validate due date >= invoice date (handled by Pydantic)
    
    # 7. Check invoice number uniqueness or auto-generate
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
    
    # 8. Calculate line item amounts
    line_items_data = []
    for li in payload.lineItems:
        amounts = calculate_line_item_amounts(li)
        line_items_data.append({
            'data': li,
            'amounts': amounts
        })
    
    # 9. Calculate invoice totals
    subtotal = sum(li['amounts']['amount'] for li in line_items_data)
    tax_total = sum(li['amounts']['tax_amount'] for li in line_items_data)
    total = subtotal + tax_total
    
    # 10. Set initial status based on due date
    initial_status = 'unpaid'  # payment_status field
    
    # 11. Insert invoice record
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
        payment_status=initial_status,
        notes=payload.notes,
        created_by=user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(invoice)
    
    # 12. Insert line items
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
    
    # 13. Increment tenant invoice count (TODO)
    
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
    
    return build_invoice_response(invoice, customer, line_items_query)


@router.put("/{id}", response_model=InvoiceResponse)
def update_invoice(
    id: str,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update existing invoice (only if status is Pending or Draft)"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Verify invoice exists and belongs to tenant
    invoice = db.query(Invoice).filter(
        Invoice.id == id,
        Invoice.tenant_id == tenant_id
    ).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # 3. Check if invoice can be edited
    if invoice.payment_status == 'paid':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit paid invoices"
        )
    
    # Check for receipts allocated
    receipt_count = db.query(func.count(ReceiptAllocation.id)).filter(
        ReceiptAllocation.invoice_id == id
    ).scalar()
    
    if receipt_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit invoices with receipts allocated"
        )
    
    # 4. Validate all fields (same as POST)
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
    
    # 5. Delete existing line items
    db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == id
    ).delete()
    
    # 6. Insert new line items with recalculated amounts
    line_items_data = []
    for li in payload.lineItems:
        amounts = calculate_line_item_amounts(li)
        line_items_data.append({
            'data': li,
            'amounts': amounts
        })
    
    # 7. Recalculate invoice totals
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
    
    # 8. Update invoice record
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
    
    return build_invoice_response(invoice, customer, line_items_query)


@router.delete("/{id}")
def delete_invoice(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete invoice (only if no payments received)"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Verify invoice exists
    invoice = db.query(Invoice).filter(
        Invoice.id == id,
        Invoice.tenant_id == tenant_id
    ).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # 3. Check for receipt allocations
    receipt_count = db.query(func.count(ReceiptAllocation.id)).filter(
        ReceiptAllocation.invoice_id == id
    ).scalar()
    
    if receipt_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete invoices with receipts"
        )
    
    # 4. Check for credit notes
    credit_note_count = db.query(func.count(CreditNote.id)).filter(
        CreditNote.invoice_id == id
    ).scalar()
    
    if credit_note_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete invoices with credit notes"
        )
    
    # 5. Delete line items first
    db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == id
    ).delete()
    
    # 6. Delete invoice
    db.delete(invoice)
    
    # 7. Decrement tenant invoice count (TODO)
    
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
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Fetch invoice with all details
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
    
    # 3. Get company data
    from app.models.company import Company
    company = db.query(Company).filter(Company.tenant_id == tenant_id).first()
    
    # 4. Get line items
    line_items = db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == id
    ).all()
    
    # 5. Prepare invoice data
    from app.services.pdf import generate_invoice_pdf
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
                "totalAmount": float(li.total_amount)
            }
            for li in line_items
        ],
        "subtotal": float(invoice.subtotal),
        "taxAmount": float(invoice.tax_amount),
        "discountAmount": float(invoice.discount_amount),
        "total": float(invoice.total),
        "notes": invoice.notes or "",
        "terms": invoice.terms or ""
    }
    
    company_data = {
        "name": company.name if company else "Company Name",
        "address": company.address if company else "",
        "taxId": company.tax_id if company else ""
    }
    
    # 6. Generate PDF
    pdf_content = generate_invoice_pdf(invoice_data, company_data)
    
    # 7. Return PDF as download
    from fastapi.responses import Response
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
    # 1. Verify invoice exists
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
    
    # 2. Get company data
    from app.models.company import Company
    company = db.query(Company).filter(Company.tenant_id == tenant_id).first()
    
    # 3. Get line items
    line_items = db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == id
    ).all()
    
    # 4. Prepare invoice data
    from app.services.pdf import generate_invoice_pdf
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
                "totalAmount": float(li.total_amount)
            }
            for li in line_items
        ],
        "subtotal": float(invoice.subtotal),
        "taxAmount": float(invoice.tax_amount),
        "discountAmount": float(invoice.discount_amount),
        "total": float(invoice.total),
        "notes": invoice.notes or "",
        "terms": invoice.terms or ""
    }
    
    company_data = {
        "name": company.name if company else "Company Name",
        "address": company.address if company else "",
        "taxId": company.tax_id if company else ""
    }
    
    # 5. Generate PDF
    pdf_content = generate_invoice_pdf(invoice_data, company_data)
    
    # 6. Send email with PDF attachment
    from app.services.email import send_invoice_email as send_email
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
    
    # 7. Return success response
    return {
        "success": True,
        "message": f"Invoice sent to {payload.recipientEmail}",
        "sentTo": payload.recipientEmail,
        "sentAt": datetime.utcnow().isoformat()
    }
