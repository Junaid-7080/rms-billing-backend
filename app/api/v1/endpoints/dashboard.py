from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract, and_
from datetime import datetime, date
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.invoice import Invoice
from app.models.credit_note import CreditNote
from app.models.company import Company
from app.models.customer import Customer, ClientType

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/metrics")
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get key financial metrics for dashboard overview cards"""
    tenant_id = current_user.tenant_id
    
    # Get company financial year start and currency
    company = db.query(Company).filter(Company.tenant_id == tenant_id).first()
    currency = company.currency if company else "INR"
    
    # Calculate financial year start date
    today = date.today()
    if company and company.financial_year_start:
        fy_month, fy_day = company.financial_year_start.month, company.financial_year_start.day
        if today.month < fy_month or (today.month == fy_month and today.day < fy_day):
            fy_start = date(today.year - 1, fy_month, fy_day)
        else:
            fy_start = date(today.year, fy_month, fy_day)
    else:
        fy_start = date(today.year, 4, 1)  # Default April 1st
    
    # Total Receivables (Pending + Overdue)
    total_receivables = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.status.in_(['Pending', 'Overdue'])
    ).scalar() or 0
    
    # Total Revenue (Paid invoices in current financial year)
    total_revenue = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.status == 'Paid',
        Invoice.invoice_date >= fy_start
    ).scalar() or 0
    
    # Average Collection Period
    avg_collection = db.query(
        func.avg(func.datediff(Invoice.payment_date, Invoice.invoice_date))
    ).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.status == 'Paid',
        Invoice.payment_date.isnot(None)
    ).scalar() or 0
    
    # Pending Invoices Count
    pending_count = db.query(func.count(Invoice.id)).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.status.in_(['Pending', 'Overdue'])
    ).scalar() or 0
    
    # Total Credit Notes
    total_credit_notes = db.query(func.coalesce(func.sum(CreditNote.total_credit), 0)).filter(
        CreditNote.tenant_id == tenant_id,
        CreditNote.status == 'Issued'
    ).scalar() or 0
    
    return {
        "totalReceivables": float(total_receivables),
        "totalRevenue": float(total_revenue),
        "averageCollectionPeriod": float(avg_collection),
        "pendingInvoices": pending_count,
        "totalCreditNotes": float(total_credit_notes),
        "currency": currency
    }


@router.get("/revenue-trend")
def get_revenue_trend(
    year: Optional[int] = Query(default=None),
    months: int = Query(default=12, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get monthly revenue trend data for current year vs previous year"""
    tenant_id = current_user.tenant_id
    current_year = year or datetime.now().year
    previous_year = current_year - 1
    
    # Month names mapping
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    # Current year revenue by month
    current_year_data = db.query(
        extract('month', Invoice.invoice_date).label('month_num'),
        func.coalesce(func.sum(Invoice.total), 0).label('revenue')
    ).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.status == 'Paid',
        extract('year', Invoice.invoice_date) == current_year
    ).group_by('month_num').all()
    
    # Previous year revenue by month
    previous_year_data = db.query(
        extract('month', Invoice.invoice_date).label('month_num'),
        func.coalesce(func.sum(Invoice.total), 0).label('revenue')
    ).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.status == 'Paid',
        extract('year', Invoice.invoice_date) == previous_year
    ).group_by('month_num').all()
    
    # Convert to dictionaries for easy lookup
    current_dict = {int(row.month_num): float(row.revenue) for row in current_year_data}
    previous_dict = {int(row.month_num): float(row.revenue) for row in previous_year_data}
    
    # Build result array
    result = []
    for month_num in range(1, months + 1):
        result.append({
            "month": month_names[month_num - 1],
            "revenue": current_dict.get(month_num, 0.0),
            "previousYearRevenue": previous_dict.get(month_num, 0.0)
        })
    
    return result


@router.get("/aging-analysis")
def get_aging_analysis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get accounts receivable aging analysis (invoices grouped by days overdue)"""
    tenant_id = current_user.tenant_id
    current_date = date.today()
    
    # Query with aging buckets
    aging_data = db.query(
        case(
            (func.datediff(current_date, Invoice.due_date) <= 30, '0-30'),
            (and_(func.datediff(current_date, Invoice.due_date) >= 31,
                  func.datediff(current_date, Invoice.due_date) <= 60), '31-60'),
            (and_(func.datediff(current_date, Invoice.due_date) >= 61,
                  func.datediff(current_date, Invoice.due_date) <= 90), '61-90'),
            else_='90+'
        ).label('age_range'),
        func.coalesce(func.sum(Invoice.total), 0).label('amount'),
        func.count(Invoice.id).label('count')
    ).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.status.in_(['Pending', 'Overdue'])
    ).group_by('age_range').all()
    
    # Convert to list and ensure all ranges are present
    result_dict = {row.age_range: {"amount": float(row.amount), "count": row.count} 
                   for row in aging_data}
    
    # Ensure all ranges exist with proper ordering
    ranges = ['0-30', '31-60', '61-90', '90+']
    result = []
    for age_range in ranges:
        if age_range in result_dict:
            result.append({
                "range": age_range,
                "amount": result_dict[age_range]["amount"],
                "count": result_dict[age_range]["count"]
            })
        else:
            result.append({
                "range": age_range,
                "amount": 0.0,
                "count": 0
            })
    
    return result


@router.get("/customer-revenue")
def get_customer_revenue(
    period: Optional[str] = Query(default="all", regex="^(month|quarter|year|all)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get revenue breakdown by customer type (for pie chart)"""
    tenant_id = current_user.tenant_id
    today = date.today()
    
    # Determine date filter
    date_filter = None
    if period == "month":
        date_filter = date(today.year, today.month, 1)
    elif period == "quarter":
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        date_filter = date(today.year, quarter_month, 1)
    elif period == "year":
        # Get financial year start
        company = db.query(Company).filter(Company.tenant_id == tenant_id).first()
        if company and company.financial_year_start:
            fy_month = company.financial_year_start.month
            if today.month < fy_month:
                date_filter = date(today.year - 1, fy_month, 1)
            else:
                date_filter = date(today.year, fy_month, 1)
        else:
            date_filter = date(today.year, 4, 1)  # Default April 1st
    
    # Query revenue by client type
    query = db.query(
        ClientType.name.label('type'),
        func.coalesce(func.sum(Invoice.total), 0).label('revenue')
    ).join(
        Customer, Invoice.customer_id == Customer.id
    ).join(
        ClientType, Customer.client_type_id == ClientType.id
    ).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.status == 'Paid'
    )
    
    # Apply date filter if specified
    if date_filter:
        query = query.filter(Invoice.invoice_date >= date_filter)
    
    revenue_data = query.group_by(ClientType.name).order_by(func.sum(Invoice.total).desc()).all()
    
    # Calculate total revenue and percentages
    total_revenue = sum(float(row.revenue) for row in revenue_data)
    
    result = []
    for row in revenue_data:
        revenue = float(row.revenue)
        percentage = (revenue / total_revenue * 100) if total_revenue > 0 else 0
        result.append({
            "type": row.type,
            "revenue": revenue,
            "percentage": round(percentage, 1)
        })
    
    return result
