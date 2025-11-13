"""
Dashboard CRUD Operations
Database-il ninnu dashboard data fetch cheyyunna functions
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, extract
from datetime import datetime, date
from decimal import Decimal
import calendar

from app.models.invoice import Invoice
from app.models.credit_note import CreditNote
from app.models.customer import Customer, ClientType
from app.models.company import Company


class DashboardCRUD:
    """
    Dashboard-inu vendi database operations
    Ella calculations um ivde cheyyunnu
    """

    @staticmethod
    def get_financial_year_start(db: Session, tenant_id: int) -> date:
        """
        Company-nte financial year start date edukkunnu
        Indian companies-inu usually April 1 aanu
        """
        company = db.query(Company).filter(
            Company.tenant_id == tenant_id
        ).first()
        
        if company and company.financial_year_start:
            return company.financial_year_start
        
        # Default: Current year April 1 (Indian FY)
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        # April to March is FY, so if before April, previous year
        if current_month < 4:
            return date(current_year - 1, 4, 1)
        return date(current_year, 4, 1)

    @staticmethod
    def get_total_receivables(db: Session, tenant_id: int) -> Decimal:
        """
        Total unpaid invoices amount
        Pending + Overdue status ulla invoices
        """
        result = db.query(
            func.coalesce(func.sum(Invoice.total), 0)
        ).filter(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.status.in_(['Pending', 'Overdue'])
            )
        ).scalar()
        
        return Decimal(str(result))

    @staticmethod
    def get_total_revenue(db: Session, tenant_id: int, fy_start: date) -> Decimal:
        """
        Current financial year-ile total revenue
        Paid invoices mathram consider cheyyunnu
        """
        result = db.query(
            func.coalesce(func.sum(Invoice.total), 0)
        ).filter(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.status == 'Paid',
                Invoice.invoice_date >= fy_start
            )
        ).scalar()
        
        return Decimal(str(result))

    @staticmethod
    def get_average_collection_period(db: Session, tenant_id: int) -> float:
        """
        Average days to collect payment
        Payment date - Invoice date-nte average
        """
        result = db.query(
            func.coalesce(
                func.avg(
                    func.datediff(Invoice.payment_date, Invoice.invoice_date)
                ),
                0
            )
        ).filter(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.status == 'Paid',
                Invoice.payment_date.isnot(None)
            )
        ).scalar()
        
        return float(result) if result else 0.0

    @staticmethod
    def get_pending_invoices_count(db: Session, tenant_id: int) -> int:
        """
        Pending/Overdue invoices count
        Ethrayennam invoices kanikkan vendi
        """
        count = db.query(func.count(Invoice.id)).filter(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.status.in_(['Pending', 'Overdue'])
            )
        ).scalar()
        
        return count or 0

    @staticmethod
    def get_total_credit_notes(db: Session, tenant_id: int) -> Decimal:
        """
        Total credit notes amount
        Issued status ulla credit notes mathram
        """
        result = db.query(
            func.coalesce(func.sum(CreditNote.total_credit), 0)
        ).filter(
            and_(
                CreditNote.tenant_id == tenant_id,
                CreditNote.status == 'Issued'
            )
        ).scalar()
        
        return Decimal(str(result))

    @staticmethod
    def get_currency(db: Session, tenant_id: int) -> str:
        """
        Company-nte currency setting
        Default INR aanu
        """
        company = db.query(Company).filter(
            Company.tenant_id == tenant_id
        ).first()
        
        return company.currency if company else "INR"

    @staticmethod
    def get_monthly_revenue_trend(
        db: Session,
        tenant_id: int,
        year: Optional[int] = None,
        months: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Monthly revenue trend for line chart
        Current year um previous year um compare cheyyunnu
        """
        current_year = year or datetime.now().year
        previous_year = current_year - 1
        
        # Month names Malayalam-il അല്ല, English short names
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Current year revenue
        current_revenue = db.query(
            extract('month', Invoice.invoice_date).label('month_num'),
            func.coalesce(func.sum(Invoice.total), 0).label('revenue')
        ).filter(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.status == 'Paid',
                extract('year', Invoice.invoice_date) == current_year
            )
        ).group_by('month_num').all()
        
        # Previous year revenue
        previous_revenue = db.query(
            extract('month', Invoice.invoice_date).label('month_num'),
            func.coalesce(func.sum(Invoice.total), 0).label('revenue')
        ).filter(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.status == 'Paid',
                extract('year', Invoice.invoice_date) == previous_year
            )
        ).group_by('month_num').all()
        
        # Convert to dict for easy lookup
        current_dict = {int(row.month_num): float(row.revenue) for row in current_revenue}
        previous_dict = {int(row.month_num): float(row.revenue) for row in previous_revenue}
        
        # Build result array
        result = []
        for month_num in range(1, months + 1):
            result.append({
                'month': month_names[month_num - 1],
                'revenue': current_dict.get(month_num, 0.0),
                'previousYearRevenue': previous_dict.get(month_num, 0.0)
            })
        
        return result

    @staticmethod
    def get_aging_analysis(db: Session, tenant_id: int) -> List[Dict[str, Any]]:
        """
        Accounts receivable aging analysis
        0-30, 31-60, 61-90, 90+ days-il group cheyyunnu
        """
        today = date.today()
        
        # SQL CASE statement using SQLAlchemy
        age_range = case(
            (func.datediff(today, Invoice.due_date) <= 30, '0-30'),
            (func.datediff(today, Invoice.due_date).between(31, 60), '31-60'),
            (func.datediff(today, Invoice.due_date).between(61, 90), '61-90'),
            else_='90+'
        ).label('age_range')
        
        results = db.query(
            age_range,
            func.coalesce(func.sum(Invoice.total), 0).label('amount'),
            func.count(Invoice.id).label('count')
        ).filter(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.status.in_(['Pending', 'Overdue'])
            )
        ).group_by(age_range).all()
        
        # Convert to list of dicts with proper ordering
        range_order = {'0-30': 1, '31-60': 2, '61-90': 3, '90+': 4}
        aging_data = [
            {
                'range': row.age_range,
                'amount': float(row.amount),
                'count': row.count
            }
            for row in results
        ]
        
        # Sort by range order
        aging_data.sort(key=lambda x: range_order.get(x['range'], 5))
        
        # Ensure all 4 buckets present (zero fill if missing)
        all_ranges = ['0-30', '31-60', '61-90', '90+']
        existing_ranges = {item['range'] for item in aging_data}
        
        for range_name in all_ranges:
            if range_name not in existing_ranges:
                aging_data.append({
                    'range': range_name,
                    'amount': 0.0,
                    'count': 0
                })
        
        # Re-sort after adding missing buckets
        aging_data.sort(key=lambda x: range_order.get(x['range'], 5))
        
        return aging_data

    @staticmethod
    def get_customer_revenue_breakdown(
        db: Session,
        tenant_id: int,
        period: str = 'all'
    ) -> List[Dict[str, Any]]:
        """
        Customer type wise revenue breakdown
        Enterprise, SMB, Startup, Individual oke
        Period filter: month, quarter, year, all
        """
        # Determine date filter
        date_filter = None
        today = date.today()
        
        if period == 'month':
            # Current month start
            date_filter = date(today.year, today.month, 1)
        elif period == 'quarter':
            # Current quarter start
            quarter = (today.month - 1) // 3
            month = quarter * 3 + 1
            date_filter = date(today.year, month, 1)
        elif period == 'year':
            # Financial year start
            # This should ideally use company FY, simplified here
            if today.month < 4:
                date_filter = date(today.year - 1, 4, 1)
            else:
                date_filter = date(today.year, 4, 1)
        # else: period == 'all', no filter
        
        # Query revenue by client type
        query = db.query(
            ClientType.name.label('type'),
            func.coalesce(func.sum(Invoice.total), 0).label('revenue')
        ).join(
            Customer, Invoice.customer_id == Customer.id
        ).join(
            ClientType, Customer.client_type_id == ClientType.id
        ).filter(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.status == 'Paid'
            )
        )
        
        # Apply date filter if needed
        if date_filter:
            query = query.filter(Invoice.invoice_date >= date_filter)
        
        results = query.group_by(ClientType.name).order_by(
            func.sum(Invoice.total).desc()
        ).all()
        
        # Calculate total revenue for percentage
        total_revenue = sum(float(row.revenue) for row in results)
        
        # Build response with percentages
        revenue_data = []
        for row in results:
            revenue = float(row.revenue)
            percentage = (revenue / total_revenue * 100) if total_revenue > 0 else 0.0
            
            revenue_data.append({
                'type': row.type,
                'revenue': revenue,
                'percentage': round(percentage, 2)
            })
        
        return revenue_data