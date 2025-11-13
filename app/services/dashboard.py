"""
Dashboard Service Layer
Business logic for dashboard operations
CRUD um API endpoint um-idakk ulla layer
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.crud.dashboard import DashboardCRUD
from app.schemas.dashboard import (
    DashboardMetrics,
    MonthlyRevenue,
    AgingBucket,
    CustomerTypeRevenue
)


class DashboardService:
    """
    Dashboard business logic
    CRUD functions call cheythu, validation um transformation um cheyyunnu
    """

    @staticmethod
    def get_dashboard_metrics(db: Session, tenant_id: int) -> DashboardMetrics:
        """
        Dashboard-ile main metrics fetch cheyyunnu
        Top-il kanikkunna 6 cards-inu data
        
        Ivde ellam parallel queries alla, sequential aanu
        Real production-il parallel queries use cheyyam performance-inu
        """
        # Get financial year start
        fy_start = DashboardCRUD.get_financial_year_start(db, tenant_id)
        
        # Fetch all metrics
        # Ividuthe preshnam: oru oru metric-inum separate query
        # Optimization: Single complex query with multiple aggregations
        total_receivables = DashboardCRUD.get_total_receivables(db, tenant_id)
        total_revenue = DashboardCRUD.get_total_revenue(db, tenant_id, fy_start)
        avg_collection = DashboardCRUD.get_average_collection_period(db, tenant_id)
        pending_count = DashboardCRUD.get_pending_invoices_count(db, tenant_id)
        total_credit = DashboardCRUD.get_total_credit_notes(db, tenant_id)
        currency = DashboardCRUD.get_currency(db, tenant_id)
        
        # Build response schema
        return DashboardMetrics(
            totalReceivables=total_receivables,
            totalRevenue=total_revenue,
            averageCollectionPeriod=avg_collection,
            pendingInvoices=pending_count,
            totalCreditNotes=total_credit,
            currency=currency
        )

    @staticmethod
    def get_revenue_trend(
        db: Session,
        tenant_id: int,
        year: Optional[int] = None,
        months: int = 12
    ) -> List[MonthlyRevenue]:
        """
        Monthly revenue trend data
        Line chart-il current year vs previous year kanikkunnu
        
        Args:
            year: Which year to show (default: current year)
            months: How many months (default: 12)
        """
        # Validation
        if months < 1 or months > 12:
            months = 12
        
        if year is None:
            year = datetime.now().year
        
        # Fetch trend data from CRUD
        trend_data = DashboardCRUD.get_monthly_revenue_trend(
            db, tenant_id, year, months
        )
        
        # Convert to Pydantic models
        return [
            MonthlyRevenue(
                month=item['month'],
                revenue=item['revenue'],
                previousYearRevenue=item['previousYearRevenue']
            )
            for item in trend_data
        ]

    @staticmethod
    def get_aging_analysis(db: Session, tenant_id: int) -> List[AgingBucket]:
        """
        Receivables aging analysis
        Bar chart-il 4 buckets kanikkunnu
        
        Business rules:
        - Only unpaid invoices (Pending/Overdue)
        - Group by days overdue
        - Always return 4 buckets (zero fill if empty)
        """
        aging_data = DashboardCRUD.get_aging_analysis(db, tenant_id)
        
        # Convert to Pydantic models
        return [
            AgingBucket(
                range=item['range'],
                amount=item['amount'],
                count=item['count']
            )
            for item in aging_data
        ]

    @staticmethod
    def get_customer_revenue(
        db: Session,
        tenant_id: int,
        period: str = 'all'
    ) -> List[CustomerTypeRevenue]:
        """
        Customer type wise revenue breakdown
        Pie chart-il kanikkunnu
        
        Period options:
        - month: Current month revenue
        - quarter: Current quarter revenue
        - year: Current financial year revenue
        - all: All time revenue
        """
        # Validate period
        valid_periods = ['month', 'quarter', 'year', 'all']
        if period not in valid_periods:
            period = 'all'
        
        # Fetch revenue breakdown
        revenue_data = DashboardCRUD.get_customer_revenue_breakdown(
            db, tenant_id, period
        )
        
        # Convert to Pydantic models
        result = [
            CustomerTypeRevenue(
                type=item['type'],
                revenue=item['revenue'],
                percentage=item['percentage']
            )
            for item in revenue_data
        ]
        
        # Business validation: Ensure percentages sum to 100
        # (May have rounding errors, but close to 100)
        total_percentage = sum(item.percentage for item in result)
        
        # If percentages don't add up, adjust the largest one
        # Production-il better rounding algorithm use cheyyam
        if result and abs(total_percentage - 100.0) > 0.01:
            diff = 100.0 - total_percentage
            result[0].percentage += diff
            result[0].percentage = round(result[0].percentage, 2)
        
        return result

    @staticmethod
    def validate_dashboard_access(db: Session, tenant_id: int) -> bool:
        """
        Check if tenant has access to dashboard
        Trial expired, subscription issues check cheyyunnu
        
        Production-il implement cheyyendath:
        - Trial period check
        - Subscription status check
        - Feature access control
        """
        # Basic validation - ivde simple check mathram
        # Real implementation-il Subscription model check cheyyum
        
        # For now, always return True
        # TODO: Implement proper tenant/subscription checks
        return True