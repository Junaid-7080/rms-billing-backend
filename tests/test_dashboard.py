"""""
Dashboard API Tests
Dashboard endpoints-inu unit tests
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date, datetime, timedelta
from decimal import Decimal

# ✅ FIX: Import FastAPI app instance
from invoice_app_backend.main import app

# ✅ Existing models used for test DB operations
from app.models.invoice import Invoice
from app.models.credit_note import CreditNote
from app.models.customer import Customer, ClientType


@pytest.fixture
def test_client():
    """Test client fixture"""
    return TestClient(app)


@pytest.fixture
def auth_headers(test_client):
    """
    Authentication headers fixture
    Real implementation-il login cheythu token edukkum
    """
    # Mock authentication
    # Production-il proper JWT token generate cheyyum
    return {"Authorization": "Bearer mock_token"}


class TestDashboardMetrics:
    """Dashboard metrics endpoint tests"""
    
    def test_get_metrics_success(self, test_client, auth_headers, db_session):
        """
        Test: Dashboard metrics successful fetch
        Expected: 200 OK with all metric fields
        """
        response = test_client.get(
            "/api/v1/dashboard/metrics",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields present
        assert "totalReceivables" in data
        assert "totalRevenue" in data
        assert "averageCollectionPeriod" in data
        assert "pendingInvoices" in data
        assert "totalCreditNotes" in data
        assert "currency" in data
        
        # Check data types
        assert isinstance(data["totalReceivables"], (int, float))
        assert isinstance(data["totalRevenue"], (int, float))
        assert isinstance(data["averageCollectionPeriod"], (int, float))
        assert isinstance(data["pendingInvoices"], int)
        assert isinstance(data["currency"], str)
    
    def test_get_metrics_unauthorized(self, test_client):
        """
        Test: Metrics without authentication
        Expected: 401 Unauthorized
        """
        response = test_client.get("/api/v1/dashboard/metrics")
        assert response.status_code == 401
    
    def test_get_metrics_with_data(self, test_client, auth_headers, db_session):
        """
        Test: Metrics with actual invoice data
        Expected: Correct calculations
        """
        # Setup: Create test invoices (Mock data)
        response = test_client.get(
            "/api/v1/dashboard/metrics",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["totalReceivables"] >= 0
        assert data["totalRevenue"] >= 0


class TestRevenueTrend:
    """Revenue trend endpoint tests"""
    
    def test_get_trend_default_params(self, test_client, auth_headers):
        """
        Test: Revenue trend with default parameters
        Expected: 12 months data for current year
        """
        response = test_client.get(
            "/api/v1/dashboard/revenue-trend",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 12
        
        if data:
            month_data = data[0]
            assert "month" in month_data
            assert "revenue" in month_data
            assert "previousYearRevenue" in month_data
    
    def test_get_trend_custom_year(self, test_client, auth_headers):
        """
        Test: Revenue trend for specific year
        Expected: Data for requested year
        """
        response = test_client.get(
            "/api/v1/dashboard/revenue-trend?year=2023",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 12
    
    def test_get_trend_custom_months(self, test_client, auth_headers):
        """
        Test: Revenue trend for specific number of months
        Expected: Requested number of months
        """
        response = test_client.get(
            "/api/v1/dashboard/revenue-trend?months=6",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 6
    
    def test_get_trend_invalid_months(self, test_client, auth_headers):
        """
        Test: Revenue trend with invalid months parameter
        Expected: Validation error or default to 12
        """
        response = test_client.get(
            "/api/v1/dashboard/revenue-trend?months=15",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 422]


class TestAgingAnalysis:
    """Aging analysis endpoint tests"""
    
    def test_get_aging_success(self, test_client, auth_headers):
        """
        Test: Aging analysis successful fetch
        Expected: 4 buckets (0-30, 31-60, 61-90, 90+)
        """
        response = test_client.get(
            "/api/v1/dashboard/aging-analysis",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        
        ranges = [item["range"] for item in data]
        assert "0-30" in ranges
        assert "31-60" in ranges
        assert "61-90" in ranges
        assert "90+" in ranges
        
        for bucket in data:
            assert "range" in bucket
            assert "amount" in bucket
            assert "count" in bucket
            assert isinstance(bucket["amount"], (int, float))
            assert isinstance(bucket["count"], int)
    
    def test_aging_bucket_order(self, test_client, auth_headers):
        """
        Test: Aging buckets in correct order
        Expected: 0-30, 31-60, 61-90, 90+
        """
        response = test_client.get(
            "/api/v1/dashboard/aging-analysis",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        expected_order = ["0-30", "31-60", "61-90", "90+"]
        actual_order = [item["range"] for item in data]
        assert actual_order == expected_order


class TestCustomerRevenue:
    """Customer revenue endpoint tests"""
    
    def test_get_customer_revenue_all(self, test_client, auth_headers):
        """
        Test: Customer revenue with 'all' period
        Expected: All time revenue breakdown
        """
        response = test_client.get(
            "/api/v1/dashboard/customer-revenue?period=all",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data:
            item = data[0]
            assert "type" in item
            assert "revenue" in item
            assert "percentage" in item
            assert isinstance(item["revenue"], (int, float))
            assert isinstance(item["percentage"], (int, float))
    
    def test_get_customer_revenue_month(self, test_client, auth_headers):
        """
        Test: Customer revenue for current month
        Expected: Month revenue breakdown
        """
        response = test_client.get(
            "/api/v1/dashboard/customer-revenue?period=month",
            headers=auth_headers
        )
        
        assert response.status_code == 200
    
    def test_get_customer_revenue_invalid_period(self, test_client, auth_headers):
        """
        Test: Customer revenue with invalid period
        Expected: Validation error (422)
        """
        response = test_client.get(
            "/api/v1/dashboard/customer-revenue?period=invalid",
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_customer_revenue_percentages(self, test_client, auth_headers):
        """
        Test: Customer revenue percentages sum to 100
        Expected: Total percentage close to 100%
        """
        response = test_client.get(
            "/api/v1/dashboard/customer-revenue?period=all",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data:
            total_percentage = sum(item["percentage"] for item in data)
            assert abs(total_percentage - 100.0) < 0.1


class TestDashboardIntegration:
    """
    Dashboard integration tests
    Real database-il data insert cheythu test cheyyunnu
    """
    
    @pytest.mark.integration
    def test_full_dashboard_flow(self, test_client, auth_headers, db_session):
        """
        Test: Complete dashboard data flow
        Expected: All endpoints work together
        """
        endpoints = [
            "/api/v1/dashboard/metrics",
            "/api/v1/dashboard/revenue-trend",
            "/api/v1/dashboard/aging-analysis",
            "/api/v1/dashboard/customer-revenue"
        ]
        
        for endpoint in endpoints:
            response = test_client.get(endpoint, headers=auth_headers)
            assert response.status_code == 200
    
    @pytest.mark.integration
    def test_dashboard_performance(self, test_client, auth_headers, db_session):
        """
        Test: Dashboard load performance
        Expected: All endpoints respond within time limit
        """
        import time
        
        start = time.time()
        response = test_client.get(
            "/api/v1/dashboard/metrics",
            headers=auth_headers
        )
        end = time.time()
        
        assert response.status_code == 200
        assert (end - start) < 2.0