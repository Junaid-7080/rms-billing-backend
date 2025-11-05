# 🚀 RMS Billing Software - API Quick Reference

## 📍 Base URL
```
http://localhost:8000/api/v1
```

## 🔐 Authentication Header
```
Authorization: Bearer <access_token>
```

---

## 📚 Complete API List (53 Endpoints)

### 1️⃣ Authentication (7 APIs)

```http
POST   /auth/register              # Register new user
POST   /auth/verify-email          # Verify email
POST   /auth/login                 # Login
POST   /auth/refresh               # Refresh token
POST   /auth/logout                # Logout
POST   /auth/forgot-password       # Request password reset
POST   /auth/reset-password        # Reset password
```

### 2️⃣ Tenant Management (4 APIs)

```http
GET    /tenants/me                 # Get current tenant
PUT    /tenants/me                 # Update tenant
GET    /tenants/subscription       # Get subscription status
POST   /tenants/upgrade            # Upgrade plan
```

### 3️⃣ Dashboard (4 APIs)

```http
GET    /dashboard/metrics          # Key metrics
GET    /dashboard/revenue-trend    # Revenue chart data
GET    /dashboard/aging-analysis   # Aging report
GET    /dashboard/customer-revenue # Top customers
```

### 4️⃣ Company Profile (2 APIs)

```http
GET    /company                    # Get company profile
POST   /company                    # Create/update company
```

### 5️⃣ Customers (5 APIs)

```http
GET    /customers                  # List customers
GET    /customers/{id}             # Get customer
POST   /customers                  # Create customer
PUT    /customers/{id}             # Update customer
DELETE /customers/{id}             # Delete customer
```

### 6️⃣ Service Types (4 APIs)

```http
GET    /service-types              # List service types
POST   /service-types              # Create service type
PUT    /service-types/{id}         # Update service type
DELETE /service-types/{id}         # Delete service type
```

### 7️⃣ Client Types (4 APIs)

```http
GET    /client-types               # List client types
POST   /client-types               # Create client type
PUT    /client-types/{id}          # Update client type
DELETE /client-types/{id}          # Delete client type
```

### 8️⃣ Account Managers (1 API)

```http
GET    /account-managers           # List account managers
```

### 9️⃣ Invoices (7 APIs)

```http
GET    /invoices                   # List invoices
GET    /invoices/{id}              # Get invoice
POST   /invoices                   # Create invoice
PUT    /invoices/{id}              # Update invoice
DELETE /invoices/{id}              # Delete invoice
GET    /invoices/{id}/pdf          # Generate PDF
POST   /invoices/{id}/send-email   # Email invoice
```

### 🔟 Receipts (3 APIs)

```http
GET    /receipts                   # List receipts
GET    /receipts/{id}              # Get receipt
POST   /receipts                   # Create receipt
```

### 1️⃣1️⃣ Credit Notes (3 APIs)

```http
GET    /credit-notes               # List credit notes
GET    /credit-notes/{id}          # Get credit note
POST   /credit-notes               # Create credit note
```

### 1️⃣2️⃣ GST Settings (2 APIs)

```http
GET    /gst-settings               # Get GST settings
POST   /gst-settings               # Update GST settings
```

### 1️⃣3️⃣ Helpers (6 APIs)

```http
GET    /invoices/next-number                    # Next invoice number
GET    /receipts/next-number                    # Next receipt number
GET    /credit-notes/next-number                # Next credit note number
GET    /customers/{id}/pending-invoices         # Unpaid invoices
GET    /customers/{id}/paid-invoices            # Paid invoices
GET    /reports/export                          # Export CSV
```

---

## 🎯 Common Request Examples

### Register User
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "firstName": "John",
    "lastName": "Doe",
    "companyName": "Acme Corp",
    "companySlug": "acme-corp"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
```

### Create Customer
```bash
curl -X POST http://localhost:8000/api/v1/customers \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ABC Company",
    "email": "contact@abc.com",
    "phone": "+91 9876543210",
    "address": "123 Street, City"
  }'
```

### Create Invoice
```bash
curl -X POST http://localhost:8000/api/v1/invoices \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "invoiceNumber": "INV-2024-001",
    "invoiceDate": "2024-01-15",
    "dueDate": "2024-02-14",
    "customerId": "customer-uuid",
    "lineItems": [
      {
        "serviceType": "service-uuid",
        "description": "Web Development",
        "quantity": 1,
        "rate": 10000.00,
        "taxRate": 18.0
      }
    ]
  }'
```

### Get Invoice PDF
```bash
curl -X GET http://localhost:8000/api/v1/invoices/{id}/pdf \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output invoice.pdf
```

---

## 📊 Query Parameters

### Pagination
```
?page=1&size=20
```

### Search & Filter
```
?search=keyword
?status=paid
?customerId=uuid
?fromDate=2024-01-01
?toDate=2024-12-31
```

### Dashboard
```
?period=monthly&months=6
?limit=10
```

---

## 🔑 Response Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |
| 423 | Locked (Trial expired) |
| 500 | Server Error |

---

## 🎯 Testing URLs

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **Root**: http://localhost:8000/

---

## ✅ Features Summary

- ✅ 53 REST API Endpoints
- ✅ JWT Authentication
- ✅ Multi-tenant SaaS
- ✅ PDF Generation
- ✅ Email Service
- ✅ Trial Management
- ✅ Dashboard Analytics
- ✅ Complete CRUD Operations

---

**Server Running**: http://localhost:8000
**Documentation**: http://localhost:8000/docs
