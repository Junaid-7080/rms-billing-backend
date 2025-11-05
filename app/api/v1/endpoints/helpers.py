from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from datetime import datetime, date
from typing import Optional, List
import io
import csv

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.invoice import Invoice
from app.models.receipt import Receipt, ReceiptAllocation
from app.models.credit_note import CreditNote
from app.models.customer import Customer

router = APIRouter(tags=["Helpers"])


# Next Number APIs
@router.get("/api/v1/invoices/next-number")
def get_next_invoice_number(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get next available invoice number for auto-generation"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Get current year
    current_year = datetime.now().year
    
    # 3. Find highest invoice number for current year
    pattern = f"INV-{current_year}-%"
    last_invoice = db.query(Invoice).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.invoice_number.like(pattern)
    ).order_by(Invoice.invoice_number.desc()).first()
    
    # 4. Increment sequence by 1
    if last_invoice:
        # Extract sequence number from last invoice (e.g., "INV-2024-0123" -> 123)
        try:
            last_number = last_invoice.invoice_number.split('-')[-1]
            sequence = int(last_number) + 1
        except (ValueError, IndexError):
            sequence = 1
    else:
        sequence = 1
    
    # 5. Format as INV-YYYY-###
    next_number = f"INV-{current_year}-{sequence:04d}"
    
    # 6. Return next number
    return {
        "nextNumber": next_number,
        "pattern": "INV-YYYY-###",
        "year": current_year,
        "sequence": sequence
    }


@router.get("/api/v1/receipts/next-number")
def get_next_receipt_number(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get next available receipt number"""
    tenant_id = current_user.tenant_id
    current_year = datetime.now().year
    
    pattern = f"RCT-{current_year}-%"
    last_receipt = db.query(Receipt).filter(
        Receipt.tenant_id == tenant_id,
        Receipt.receipt_number.like(pattern)
    ).order_by(Receipt.receipt_number.desc()).first()
    
    if last_receipt:
        try:
            last_number = last_receipt.receipt_number.split('-')[-1]
            sequence = int(last_number) + 1
        except (ValueError, IndexError):
            sequence = 1
    else:
        sequence = 1
    
    next_number = f"RCT-{current_year}-{sequence:04d}"
    
    return {
        "nextNumber": next_number,
        "pattern": "RCT-YYYY-###",
        "year": current_year,
        "sequence": sequence
    }


@router.get("/api/v1/credit-notes/next-number")
def get_next_credit_note_number(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get next available credit note number"""
    tenant_id = current_user.tenant_id
    current_year = datetime.now().year
    
    pattern = f"CN-{current_year}-%"
    last_credit_note = db.query(CreditNote).filter(
        CreditNote.tenant_id == tenant_id,
        CreditNote.credit_note_number.like(pattern)
    ).order_by(CreditNote.credit_note_number.desc()).first()
    
    if last_credit_note:
        try:
            last_number = last_credit_note.credit_note_number.split('-')[-1]
            sequence = int(last_number) + 1
        except (ValueError, IndexError):
            sequence = 1
    else:
        sequence = 1
    
    next_number = f"CN-{current_year}-{sequence:04d}"
    
    return {
        "nextNumber": next_number,
        "pattern": "CN-YYYY-###",
        "year": current_year,
        "sequence": sequence
    }


# Customer Invoice APIs
@router.get("/api/v1/customers/{customerId}/pending-invoices")
def get_customer_pending_invoices(
    customerId: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all unpaid invoices for a specific customer (for payment allocation)"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Verify customer belongs to tenant
    customer = db.query(Customer).filter(
        Customer.id == customerId,
        Customer.tenant_id == tenant_id
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # 3-4. Query invoices with allocations
    # Using subquery to calculate paid amount
    from sqlalchemy import select
    
    paid_subquery = db.query(
        ReceiptAllocation.invoice_id,
        func.sum(ReceiptAllocation.allocated_amount).label('paid_amount')
    ).group_by(ReceiptAllocation.invoice_id).subquery()
    
    invoices = db.query(
        Invoice,
        func.coalesce(paid_subquery.c.paid_amount, 0).label('paid_amount')
    ).outerjoin(
        paid_subquery, Invoice.id == paid_subquery.c.invoice_id
    ).filter(
        Invoice.customer_id == customerId,
        Invoice.tenant_id == tenant_id,
        Invoice.payment_status.in_(['unpaid', 'partially_paid'])
    ).all()
    
    # 5. Return only invoices with outstanding amount > 0
    result = []
    for invoice, paid_amount in invoices:
        paid_amount = float(paid_amount) if paid_amount else 0.0
        outstanding = float(invoice.total) - paid_amount
        
        if outstanding > 0:
            # Calculate status
            if invoice.payment_status == 'paid':
                status_str = 'Paid'
            elif invoice.due_date < date.today():
                status_str = 'Overdue'
            else:
                status_str = 'Pending'
            
            result.append({
                "id": str(invoice.id),
                "invoiceNumber": invoice.invoice_number,
                "invoiceDate": invoice.invoice_date.isoformat(),
                "dueDate": invoice.due_date.isoformat(),
                "total": float(invoice.total),
                "paidAmount": paid_amount,
                "outstandingAmount": round(outstanding, 2),
                "status": status_str
            })
    
    # 6. Sort by invoice_date ASC (oldest first)
    result.sort(key=lambda x: x['invoiceDate'])
    
    return result


@router.get("/api/v1/customers/{customerId}/paid-invoices")
def get_customer_paid_invoices(
    customerId: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all paid invoices for a customer (for credit note issuance)"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Query invoices WHERE status = 'Paid'
    # Using subquery to calculate credit notes issued
    credit_subquery = db.query(
        CreditNote.invoice_id,
        func.sum(CreditNote.total_credit).label('credit_issued')
    ).filter(
        CreditNote.status != 'Cancelled'
    ).group_by(CreditNote.invoice_id).subquery()
    
    invoices = db.query(
        Invoice,
        func.coalesce(credit_subquery.c.credit_issued, 0).label('credit_issued')
    ).outerjoin(
        credit_subquery, Invoice.id == credit_subquery.c.invoice_id
    ).filter(
        Invoice.customer_id == customerId,
        Invoice.tenant_id == tenant_id,
        Invoice.payment_status == 'paid'
    ).all()
    
    # 3-4. Calculate available for credit
    result = []
    for invoice, credit_issued in invoices:
        credit_issued = float(credit_issued) if credit_issued else 0.0
        available = float(invoice.total) - credit_issued
        
        if available > 0:
            result.append({
                "id": str(invoice.id),
                "invoiceNumber": invoice.invoice_number,
                "invoiceDate": invoice.invoice_date.isoformat(),
                "total": float(invoice.total),
                "creditNotesIssued": credit_issued,
                "availableForCredit": round(available, 2)
            })
    
    # 5. Sort by invoice_date DESC (recent first)
    result.sort(key=lambda x: x['invoiceDate'], reverse=True)
    
    return result


# Export API
@router.get("/api/v1/reports/export")
def export_data(
    type: str = Query(..., description="invoices, customers, receipts, credit_notes"),
    format: str = Query(default="csv", regex="^(csv|xlsx)$"),
    dateFrom: Optional[date] = Query(default=None),
    dateTo: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export data as CSV or Excel"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Validate type
    valid_types = ['invoices', 'customers', 'receipts', 'credit_notes']
    if type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid type. Must be one of: {', '.join(valid_types)}"
        )
    
    # 3. Query data based on type
    if type == 'invoices':
        query = db.query(
            Invoice.invoice_number,
            Invoice.invoice_date,
            Customer.name.label('customer_name'),
            Invoice.total,
            Invoice.payment_status
        ).join(Customer, Invoice.customer_id == Customer.id).filter(
            Invoice.tenant_id == tenant_id
        )
        
        if dateFrom:
            query = query.filter(Invoice.invoice_date >= dateFrom)
        if dateTo:
            query = query.filter(Invoice.invoice_date <= dateTo)
        
        data = query.all()
        headers = ['Invoice Number', 'Invoice Date', 'Customer', 'Total', 'Status']
        rows = [[inv.invoice_number, str(inv.invoice_date), inv.customer_name, 
                 float(inv.total), inv.payment_status] for inv in data]
        filename = f"invoices-{datetime.now().strftime('%Y-%m-%d')}.csv"
        
    elif type == 'customers':
        query = db.query(Customer).filter(Customer.tenant_id == tenant_id)
        data = query.all()
        headers = ['Code', 'Name', 'Email', 'Phone', 'GST Number', 'Active']
        rows = [[c.code, c.name, c.email or '', c.phone or '', 
                 c.gst_number or '', str(c.is_active)] for c in data]
        filename = f"customers-{datetime.now().strftime('%Y-%m-%d')}.csv"
        
    elif type == 'receipts':
        query = db.query(
            Receipt.receipt_number,
            Receipt.receipt_date,
            Customer.name.label('customer_name'),
            Receipt.amount,
            Receipt.payment_method
        ).join(Customer, Receipt.customer_id == Customer.id).filter(
            Receipt.tenant_id == tenant_id
        )
        
        if dateFrom:
            query = query.filter(Receipt.receipt_date >= dateFrom)
        if dateTo:
            query = query.filter(Receipt.receipt_date <= dateTo)
        
        data = query.all()
        headers = ['Receipt Number', 'Receipt Date', 'Customer', 'Amount', 'Payment Method']
        rows = [[r.receipt_number, str(r.receipt_date), r.customer_name, 
                 float(r.amount), r.payment_method] for r in data]
        filename = f"receipts-{datetime.now().strftime('%Y-%m-%d')}.csv"
        
    elif type == 'credit_notes':
        query = db.query(
            CreditNote.credit_note_number,
            CreditNote.credit_note_date,
            Customer.name.label('customer_name'),
            CreditNote.total_credit,
            CreditNote.reason
        ).join(Customer, CreditNote.customer_id == Customer.id).filter(
            CreditNote.tenant_id == tenant_id
        )
        
        if dateFrom:
            query = query.filter(CreditNote.credit_note_date >= dateFrom)
        if dateTo:
            query = query.filter(CreditNote.credit_note_date <= dateTo)
        
        data = query.all()
        headers = ['Credit Note Number', 'Date', 'Customer', 'Total Credit', 'Reason']
        rows = [[cn.credit_note_number, str(cn.credit_note_date), cn.customer_name, 
                 float(cn.total_credit), cn.reason] for cn in data]
        filename = f"credit-notes-{datetime.now().strftime('%Y-%m-%d')}.csv"
    
    # 4. Generate CSV file (Excel support would require openpyxl library)
    if format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
        
        # 5. Stream to client
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    else:
        # Excel format would require openpyxl
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Excel export not yet implemented. Use CSV format."
        )
