"""
Dashboard Pydantic Schemas
Dashboard API responses-inu vendi schemas
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from decimal import Decimal


# 2.1 Dashboard Metrics Response
class DashboardMetrics(BaseModel):
    """
    Dashboard-ile main metric cards-inu response
    Total receivables, revenue, collection period okke kanikkunnu
    """
    totalReceivables: Decimal = Field(..., description="Unpaid invoices total")
    totalRevenue: Decimal = Field(..., description="Current year paid invoices")
    averageCollectionPeriod: float = Field(..., description="Avg days to collect payment")
    pendingInvoices: int = Field(..., description="Count of pending/overdue invoices")
    totalCreditNotes: Decimal = Field(..., description="Total credit notes issued")
    currency: str = Field(..., description="Company currency code", max_length=3)

    class Config:
        json_schema_extra = {
            "example": {
                "totalReceivables": 1234567.50,
                "totalRevenue": 2345678.00,
                "averageCollectionPeriod": 45.5,
                "pendingInvoices": 123,
                "totalCreditNotes": 123456.00,
                "currency": "INR"
            }
        }


# 2.2 Revenue Trend Response
class MonthlyRevenue(BaseModel):
    """
    Oru month-nte revenue data
    Current year um previous year um compare cheyyunnu
    """
    month: str = Field(..., description="Month name (Jan, Feb, etc.)")
    revenue: Decimal = Field(..., description="Current year revenue")
    previousYearRevenue: Decimal = Field(..., description="Previous year revenue")

    class Config:
        json_schema_extra = {
            "example": {
                "month": "Jan",
                "revenue": 4000.00,
                "previousYearRevenue": 2400.00
            }
        }


class RevenueTrendResponse(BaseModel):
    """
    12 months revenue trend
    Line chart-il kanikkan vendi
    """
    data: List[MonthlyRevenue]

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {"month": "Jan", "revenue": 4000.00, "previousYearRevenue": 2400.00},
                    {"month": "Feb", "revenue": 3000.00, "previousYearRevenue": 1398.00}
                ]
            }
        }


# 2.3 Aging Analysis Response
class AgingBucket(BaseModel):
    """
    Receivables aging bucket
    Ethra divasam overdue aano ath anusarichu group cheyyunnu
    """
    range: str = Field(..., description="Days range (0-30, 31-60, 61-90, 90+)")
    amount: Decimal = Field(..., description="Total amount in this bucket")
    count: int = Field(..., description="Number of invoices in bucket")

    class Config:
        json_schema_extra = {
            "example": {
                "range": "0-30",
                "amount": 4000.00,
                "count": 15
            }
        }


class AgingAnalysisResponse(BaseModel):
    """
    Complete aging analysis
    Bar chart-il kanikkan vendi 4 buckets
    """
    data: List[AgingBucket]

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {"range": "0-30", "amount": 4000.00, "count": 15},
                    {"range": "31-60", "amount": 3000.00, "count": 8},
                    {"range": "61-90", "amount": 2000.00, "count": 5},
                    {"range": "90+", "amount": 1000.00, "count": 2}
                ]
            }
        }


# 2.4 Customer Revenue Response
class CustomerTypeRevenue(BaseModel):
    """
    Oru customer type-nte revenue
    Enterprise, SMB, Startup, Individual oke
    """
    type: str = Field(..., description="Customer type name")
    revenue: Decimal = Field(..., description="Total revenue from this type")
    percentage: float = Field(..., description="Percentage of total revenue")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "Enterprise",
                "revenue": 4000.00,
                "percentage": 40.0
            }
        }


class CustomerRevenueResponse(BaseModel):
    """
    Customer type wise revenue breakdown
    Pie chart-il kanikkan vendi
    """
    data: List[CustomerTypeRevenue]

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {"type": "Enterprise", "revenue": 4000.00, "percentage": 40.0},
                    {"type": "SMB", "revenue": 3000.00, "percentage": 30.0},
                    {"type": "Startup", "revenue": 2000.00, "percentage": 20.0},
                    {"type": "Individual", "revenue": 1000.00, "percentage": 10.0}
                ]
            }
        }


# Query Parameters
class RevenueTrendQuery(BaseModel):
    """
    Revenue trend API-inu query params
    Year um months um optional aanu
    """
    year: Optional[int] = Field(None, description="Year to fetch data for")
    months: Optional[int] = Field(12, ge=1, le=12, description="Number of months")


class CustomerRevenueQuery(BaseModel):
    """
    Customer revenue API-inu query params
    Period filter cheyyunnu
    """
    period: Optional[str] = Field(
        "all",
        description="Time period filter",
        pattern="^(month|quarter|year|all)$"
    )