"""
Dashboard API Endpoints
FastAPI route handlers for dashboard APIs
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, get_current_active_tenant
from app.models.user import User
from app.schemas.dashboard import (
    DashboardMetrics,
    MonthlyRevenue,
    AgingBucket,
    CustomerTypeRevenue
)
from app.services.dashboard import DashboardService

# Router create cheyyunnu
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/metrics", response_model=DashboardMetrics)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant)
):
    """
    Get key financial metrics for dashboard overview cards
    
    Dashboard-ile top cards-inu data:
    - Total Receivables (unpaid invoices)
    - Total Revenue (current FY paid invoices)
    - Average Collection Period (days)
    - Pending Invoices (count)
    - Total Credit Notes
    - Currency
    
    **Frontend use:**
    - Called on dashboard page load
    - Optional polling every 5 minutes
    - Display in metric cards at top
    """
    try:
        # Service layer call cheyyunnu
        metrics = DashboardService.get_dashboard_metrics(db, tenant_id)
        return metrics
    
    except Exception as e:
        # Log error (production-il proper logging)
        print(f"Dashboard metrics error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch dashboard metrics"
        )


@router.get("/revenue-trend", response_model=List[MonthlyRevenue])
def get_revenue_trend(
    year: Optional[int] = Query(None, description="Year to fetch data for"),
    months: int = Query(12, ge=1, le=12, description="Number of months to fetch"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant)
):
    """
    Get monthly revenue trend data for current year vs previous year
    
    Line chart-il kanikkan vendi data:
    - 12 months data (or specified months)
    - Current year revenue
    - Previous year revenue for comparison
    
    **Query Parameters:**
    - year: Which year to show (default: current year)
    - months: Number of months (default: 12, max: 12)
    
    **Frontend use:**
    - Called on dashboard page load
    - RevenueChart component
    - Line chart showing revenue comparison
    """
    try:
        trend_data = DashboardService.get_revenue_trend(
            db, tenant_id, year, months
        )
        return trend_data
    
    except Exception as e:
        print(f"Revenue trend error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch revenue trend data"
        )


@router.get("/aging-analysis", response_model=List[AgingBucket])
def get_aging_analysis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant)
):
    """
    Get accounts receivable aging analysis
    
    Unpaid invoices-ne days overdue anusarichu group cheyyunnu:
    - 0-30 days
    - 31-60 days
    - 61-90 days
    - 90+ days
    
    Each bucket-il:
    - Total amount
    - Invoice count
    
    **Frontend use:**
    - Called on dashboard page load
    - AgingChart component
    - Bar chart showing receivables by age
    """
    try:
        aging_data = DashboardService.get_aging_analysis(db, tenant_id)
        return aging_data
    
    except Exception as e:
        print(f"Aging analysis error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch aging analysis"
        )


@router.get("/customer-revenue", response_model=List[CustomerTypeRevenue])
def get_customer_revenue(
    period: str = Query(
        "all",
        regex="^(month|quarter|year|all)$",
        description="Time period: month, quarter, year, all"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant)
):
    """
    Get revenue breakdown by customer type
    
    Customer types anusarichu revenue split:
    - Enterprise
    - SMB (Small & Medium Business)
    - Startup
    - Individual
    
    Each type-inu:
    - Total revenue
    - Percentage of total
    
    **Query Parameters:**
    - period: Time period filter
      - month: Current month revenue
      - quarter: Current quarter revenue
      - year: Current financial year revenue
      - all: All time revenue (default)
    
    **Frontend use:**
    - Called on dashboard page load
    - CustomerChart component
    - Pie chart showing revenue distribution
    """
    try:
        revenue_data = DashboardService.get_customer_revenue(
            db, tenant_id, period
        )
        return revenue_data
    
    except Exception as e:
        print(f"Customer revenue error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch customer revenue breakdown"
        )