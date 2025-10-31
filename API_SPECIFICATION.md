# RMS Billing Software - Complete API Specification

## Overview

This document provides a comprehensive specification of all REST API endpoints required for the RMS (Revenue Management System) Billing Software. The frontend React application requires these APIs to function as a complete multi-tenant SaaS billing system.

**Base URL**: `http://localhost:8000/api/v1`

**Authentication**: All endpoints (except public auth endpoints) require JWT Bearer token in Authorization header.

**Total Endpoints**: 46 APIs

---

## Table of Contents

1. [Authentication APIs](#1-authentication-apis) (5 endpoints)
2. [Dashboard APIs](#2-dashboard-apis) (4 endpoints)
3. [Company Profile APIs](#3-company-profile-apis) (2 endpoints)
4. [Customer Management APIs](#4-customer-management-apis) (5 endpoints)
5. [Service Type APIs](#5-service-type-apis) (4 endpoints)
6. [Client Type APIs](#6-client-type-apis) (4 endpoints)
7. [Account Manager APIs](#7-account-manager-apis) (1 endpoint)
8. [Invoice Management APIs](#8-invoice-management-apis) (7 endpoints)
9. [Receipt (Payment) APIs](#9-receipt-payment-apis) (3 endpoints)
10. [Credit Note APIs](#10-credit-note-apis) (3 endpoints)
11. [GST Settings APIs](#11-gst-settings-apis) (2 endpoints)
12. [Helper/Utility APIs](#12-helperutility-apis) (6 endpoints)
13. [Common Patterns](#13-common-patterns)

---

# 1. AUTHENTICATION APIs

## 1.1 POST /api/v1/auth/register

**Description**: Register new user and create tenant (company). Starts 14-day free trial.

**Authentication**: None (public endpoint)

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "firstName": "John",
  "lastName": "Doe",
  "companyName": "Acme Corp",
  "companySlug": "acme-corp"
}
```

**Request Schema**:
| Field | Type | Required | Validation |
|-------|------|----------|------------|
| email | string | Yes | Valid email format, unique globally |
| password | string | Yes | Min 8 chars, 1 uppercase, 1 lowercase, 1 number |
| firstName | string | Yes | Min 2 chars |
| lastName | string | No | Min 2 chars if provided |
| companyName | string | Yes | Min 2 chars |
| companySlug | string | Yes | Min 2 chars, lowercase, alphanumeric + hyphens, unique globally |

**Success Response (201 Created)**:
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "firstName": "John",
    "lastName": "Doe",
    "role": "admin",
    "emailVerified": false
  },
  "tenant": {
    "id": "uuid",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "subscriptionStatus": "trial",
    "trialStartDate": "2024-01-15T10:30:00Z",
    "trialEndDate": "2024-01-29T10:30:00Z",
    "trialDaysRemaining": 14
  },
  "message": "Registration successful. Please check your email to verify your account."
}
```

**Error Responses**:
- `400 Bad Request`: Validation errors
  ```json
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Validation failed",
      "details": {
        "email": "Email already exists",
        "password": "Password must contain at least one uppercase letter"
      }
    }
  }
  ```
- `409 Conflict`: Email or slug already exists

**Business Logic**:
1. Validate all input fields
2. Check email uniqueness across all users
3. Check company slug uniqueness across all tenants
4. Hash password using bcrypt (cost factor 12)
5. Generate unique UUIDs for user and tenant
6. Create tenant record:
   - Set `subscription_status = 'trial'`
   - Set `trial_start_date = NOW()`
   - Set `trial_end_date = NOW() + 14 days`
   - Set `is_trial_used = true`
   - Initialize usage counters to 0
7. Create user record:
   - Link to tenant via `tenant_id`
   - Set `role = 'admin'` (first user is always admin)
   - Set `email_verified = false`
8. Create subscription record:
   - Set `plan_type = 'trial'`
   - Set `is_trial = true`
   - Set trial dates
9. Generate email verification token (UUID, expires in 24 hours)
10. Store token in `email_verifications` table
11. Send welcome + verification email to user
12. Return user and tenant data (NO tokens until email verified)

**Database Operations**:
```sql
-- Check uniqueness
SELECT COUNT(*) FROM users WHERE email = ?
SELECT COUNT(*) FROM tenants WHERE slug = ?

-- Insert records
INSERT INTO tenants (id, name, slug, email, subscription_status, trial_start_date, trial_end_date, is_trial_used, ...)
INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name, role, email_verified, ...)
INSERT INTO subscriptions (id, tenant_id, plan_type, is_trial, trial_start_date, trial_end_date, ...)
INSERT INTO email_verifications (id, user_id, token, expires_at, ...)
```

**Side Effects**:
- Sends verification email
- Creates audit log entry
- May trigger analytics event

**Frontend Usage**:
- **File**: Registration page (to be created)
- **Called on**: Form submission
- **Next step**: Redirect to "Check your email" page

---

## 1.2 POST /api/v1/auth/verify-email

**Description**: Verify user's email address using verification token.

**Authentication**: None (public endpoint)

**Request Body**:
```json
{
  "token": "verification-token-uuid"
}
```

**Success Response (200 OK)**:
```json
{
  "message": "Email verified successfully. You can now log in.",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "emailVerified": true
  }
}
```

**Error Responses**:
- `400 Bad Request`: Invalid or expired token
- `404 Not Found`: Token not found
- `409 Conflict`: Email already verified

**Business Logic**:
1. Find verification record by token
2. Check if token exists
3. Check if token is not expired (< 24 hours old)
4. Check if token not already used
5. Get associated user
6. Update user:
   - Set `email_verified = true`
   - Set `email_verified_at = NOW()`
7. Mark token as used:
   - Set `is_used = true`
   - Set `used_at = NOW()`
8. Return success message

**Database Operations**:
```sql
SELECT * FROM email_verifications WHERE token = ? AND is_used = false AND expires_at > NOW()
UPDATE users SET email_verified = true, email_verified_at = NOW() WHERE id = ?
UPDATE email_verifications SET is_used = true, used_at = NOW() WHERE id = ?
```

**Frontend Usage**:
- **File**: Email verification page (to be created)
- **Called on**: Page load with token from email link
- **Next step**: Redirect to login page

---

## 1.3 POST /api/v1/auth/login

**Description**: Authenticate user and return JWT tokens. Requires verified email.

**Authentication**: None (public endpoint)

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Success Response (200 OK)**:
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "firstName": "John",
    "lastName": "Doe",
    "role": "admin",
    "emailVerified": true
  },
  "tenant": {
    "id": "uuid",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "subscriptionStatus": "trial",
    "trialDaysRemaining": 10,
    "trialEndDate": "2024-01-29T10:30:00Z"
  },
  "tokens": {
    "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expiresIn": 1800
  }
}
```

**Error Responses**:
- `400 Bad Request`: Missing email or password
- `401 Unauthorized`: Invalid credentials
- `403 Forbidden`: Email not verified or account inactive
- `423 Locked`: Trial expired and not upgraded

**Business Logic**:
1. Validate email and password provided
2. Find user by email
3. Check if user exists
4. Verify password hash matches
5. Check if email is verified
6. Check if user is active
7. Get user's tenant
8. Check tenant subscription status:
   - If trial expired and not upgraded, return 423 Locked
   - Calculate days remaining if on trial
9. Generate JWT access token (expires in 30 minutes):
   - Payload: `{ sub: user_id, tenant_id, email, role, exp }`
10. Generate JWT refresh token (expires in 7 days):
    - Payload: `{ sub: user_id, tenant_id, type: 'refresh', exp }`
11. Create session record:
    - Store refresh token
    - Store IP address
    - Store user agent
    - Set expiration
12. Update user `last_login_at = NOW()`
13. Return user, tenant, and tokens

**Database Operations**:
```sql
SELECT u.*, t.* FROM users u
JOIN tenants t ON u.tenant_id = t.id
WHERE u.email = ? AND u.is_active = true

INSERT INTO sessions (id, user_id, refresh_token, access_token, expires_at, ip_address, user_agent, ...)

UPDATE users SET last_login_at = NOW() WHERE id = ?
```

**Side Effects**:
- Creates session record
- Updates last login timestamp
- May trigger login notification email (optional)

**Frontend Usage**:
- **File**: Login page (to be created)
- **Called on**: Login form submission
- **Next step**: Store tokens, redirect to dashboard

---

## 1.4 POST /api/v1/auth/refresh

**Description**: Get new access token using refresh token.

**Authentication**: Refresh token in request body

**Request Body**:
```json
{
  "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Success Response (200 OK)**:
```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expiresIn": 1800
}
```

**Error Responses**:
- `400 Bad Request`: Missing refresh token
- `401 Unauthorized`: Invalid or expired refresh token
- `404 Not Found`: Session not found or revoked

**Business Logic**:
1. Verify refresh token signature
2. Decode token payload
3. Find session by refresh token
4. Check if session exists
5. Check if session is active (not revoked)
6. Check if session not expired
7. Get user and tenant IDs from token
8. Generate new access token with same payload
9. Update session with new access token
10. Return new access token

**Database Operations**:
```sql
SELECT * FROM sessions WHERE refresh_token = ? AND is_active = true AND expires_at > NOW()
UPDATE sessions SET access_token = ?, updated_at = NOW() WHERE id = ?
```

**Frontend Usage**:
- **File**: Axios interceptor / API utility
- **Called on**: When access token expires (401 response)
- **Next step**: Retry original request with new token

---

## 1.5 POST /api/v1/auth/logout

**Description**: Logout user and revoke session.

**Authentication**: Required (Bearer token)

**Request Body**: None

**Success Response (200 OK)**:
```json
{
  "message": "Logged out successfully"
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or missing token

**Business Logic**:
1. Extract user ID from JWT token
2. Decode access token to get session info
3. Find session record
4. Mark session as inactive:
   - Set `is_active = false`
   - Set `revoked_at = NOW()`
5. Return success message

**Database Operations**:
```sql
UPDATE sessions SET is_active = false, revoked_at = NOW()
WHERE user_id = ? AND refresh_token = ?
```

**Frontend Usage**:
- **File**: Header component, logout button
- **Called on**: Logout button click
- **Next step**: Clear local storage, redirect to login

---

# 2. DASHBOARD APIs

## 2.1 GET /api/v1/dashboard/metrics

**Description**: Get key financial metrics for dashboard overview cards.

**Authentication**: Required

**Query Parameters**: None

**Success Response (200 OK)**:
```json
{
  "totalReceivables": 1234567.50,
  "totalRevenue": 2345678.00,
  "averageCollectionPeriod": 45.5,
  "pendingInvoices": 123,
  "totalCreditNotes": 123456.00,
  "currency": "INR"
}
```

**Response Schema**:
| Field | Type | Description |
|-------|------|-------------|
| totalReceivables | number | Sum of all unpaid invoice totals |
| totalRevenue | number | Sum of all paid invoices for current financial year |
| averageCollectionPeriod | number | Average days to collect payment |
| pendingInvoices | number | Count of pending/overdue invoices |
| totalCreditNotes | number | Sum of all credit note amounts |
| currency | string | Currency code (from company settings) |

**Business Logic**:
1. Get current tenant_id from JWT
2. Get company financial year start date
3. **Total Receivables**:
   - SUM(total) from invoices WHERE status IN ('Pending', 'Overdue') AND tenant_id = ?
4. **Total Revenue**:
   - SUM(total) from invoices WHERE status = 'Paid' AND invoice_date >= financial_year_start AND tenant_id = ?
5. **Average Collection Period**:
   - Calculate: AVG(DATEDIFF(payment_date, invoice_date)) for paid invoices
   - Only include invoices with payment_date set
6. **Pending Invoices**:
   - COUNT(*) from invoices WHERE status IN ('Pending', 'Overdue') AND tenant_id = ?
7. **Total Credit Notes**:
   - SUM(total_credit) from credit_notes WHERE status = 'Issued' AND tenant_id = ?
8. Get currency from company settings
9. Return all metrics

**Database Operations**:
```sql
-- Total Receivables
SELECT COALESCE(SUM(total), 0) as total_receivables
FROM invoices
WHERE tenant_id = ? AND status IN ('Pending', 'Overdue')

-- Total Revenue
SELECT COALESCE(SUM(total), 0) as total_revenue
FROM invoices
WHERE tenant_id = ? AND status = 'Paid' AND invoice_date >= ?

-- Average Collection Period
SELECT COALESCE(AVG(DATEDIFF(payment_date, invoice_date)), 0) as avg_collection
FROM invoices
WHERE tenant_id = ? AND status = 'Paid' AND payment_date IS NOT NULL

-- Pending Invoices
SELECT COUNT(*) as pending_count
FROM invoices
WHERE tenant_id = ? AND status IN ('Pending', 'Overdue')

-- Total Credit Notes
SELECT COALESCE(SUM(total_credit), 0) as total_credit_notes
FROM credit_notes
WHERE tenant_id = ? AND status = 'Issued'

-- Currency
SELECT currency FROM companies WHERE tenant_id = ? LIMIT 1
```

**Frontend Usage**:
- **File**: `src/pages/dashboard.tsx`
- **Component**: Metric cards at top of dashboard
- **Called on**: Dashboard page load
- **Refresh**: Every 5 minutes (optional polling)

---

## 2.2 GET /api/v1/dashboard/revenue-trend

**Description**: Get monthly revenue trend data for current year vs previous year (for line chart).

**Authentication**: Required

**Query Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| year | number | No | Current year | Year to fetch data for |
| months | number | No | 12 | Number of months to fetch |

**Success Response (200 OK)**:
```json
[
  {
    "month": "Jan",
    "revenue": 4000.00,
    "previousYearRevenue": 2400.00
  },
  {
    "month": "Feb",
    "revenue": 3000.00,
    "previousYearRevenue": 1398.00
  },
  {
    "month": "Mar",
    "revenue": 2000.00,
    "previousYearRevenue": 9800.00
  }
]
```

**Business Logic**:
1. Get tenant_id from JWT
2. Determine year (from query param or current year)
3. For each month (1-12):
   - Query invoices for current year, that month
   - SUM total WHERE status = 'Paid'
   - Query invoices for previous year, same month
   - SUM total WHERE status = 'Paid'
4. Format month names as Jan, Feb, Mar, etc.
5. Return array of month objects with both years' revenue

**Database Operations**:
```sql
-- Current year revenue by month
SELECT
  MONTH(invoice_date) as month_num,
  COALESCE(SUM(total), 0) as revenue
FROM invoices
WHERE tenant_id = ?
  AND status = 'Paid'
  AND YEAR(invoice_date) = ?
GROUP BY MONTH(invoice_date)
ORDER BY month_num

-- Previous year revenue by month
SELECT
  MONTH(invoice_date) as month_num,
  COALESCE(SUM(total), 0) as revenue
FROM invoices
WHERE tenant_id = ?
  AND status = 'Paid'
  AND YEAR(invoice_date) = ?
GROUP BY MONTH(invoice_date)
ORDER BY month_num
```

**Data Transformation**:
- Convert month numbers (1-12) to month names (Jan-Dec)
- Merge current and previous year data
- Fill missing months with 0 revenue

**Frontend Usage**:
- **File**: `src/pages/dashboard.tsx`
- **Component**: `RevenueChart` component
- **Called on**: Dashboard page load
- **Chart**: Line chart showing revenue comparison

---

## 2.3 GET /api/v1/dashboard/aging-analysis

**Description**: Get accounts receivable aging analysis (invoices grouped by days overdue).

**Authentication**: Required

**Query Parameters**: None

**Success Response (200 OK)**:
```json
[
  {
    "range": "0-30",
    "amount": 4000.00,
    "count": 15
  },
  {
    "range": "31-60",
    "amount": 3000.00,
    "count": 8
  },
  {
    "range": "61-90",
    "amount": 2000.00,
    "count": 5
  },
  {
    "range": "90+",
    "amount": 1000.00,
    "count": 2
  }
]
```

**Business Logic**:
1. Get tenant_id from JWT
2. Get current date
3. Query all unpaid invoices (status = 'Pending' or 'Overdue')
4. For each invoice:
   - Calculate days overdue = DATEDIFF(current_date, due_date)
   - If days_overdue < 0, it's not yet due (skip or put in 0-30)
5. Group invoices into buckets:
   - 0-30 days: days_overdue <= 30
   - 31-60 days: 31 <= days_overdue <= 60
   - 61-90 days: 61 <= days_overdue <= 90
   - 90+ days: days_overdue > 90
6. For each bucket:
   - SUM total amounts
   - COUNT invoices
7. Return array of 4 buckets

**Database Operations**:
```sql
SELECT
  CASE
    WHEN DATEDIFF(CURRENT_DATE, due_date) <= 30 THEN '0-30'
    WHEN DATEDIFF(CURRENT_DATE, due_date) BETWEEN 31 AND 60 THEN '31-60'
    WHEN DATEDIFF(CURRENT_DATE, due_date) BETWEEN 61 AND 90 THEN '61-90'
    ELSE '90+'
  END as age_range,
  COALESCE(SUM(total), 0) as amount,
  COUNT(*) as count
FROM invoices
WHERE tenant_id = ?
  AND status IN ('Pending', 'Overdue')
GROUP BY age_range
ORDER BY
  CASE age_range
    WHEN '0-30' THEN 1
    WHEN '31-60' THEN 2
    WHEN '61-90' THEN 3
    ELSE 4
  END
```

**Frontend Usage**:
- **File**: `src/pages/dashboard.tsx`
- **Component**: `AgingChart` component
- **Called on**: Dashboard page load
- **Chart**: Bar chart showing receivables by age

---

## 2.4 GET /api/v1/dashboard/customer-revenue

**Description**: Get revenue breakdown by customer type (for pie chart).

**Authentication**: Required

**Query Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| period | string | No | all | Time period: month, quarter, year, all |

**Success Response (200 OK)**:
```json
[
  {
    "type": "Enterprise",
    "revenue": 4000.00,
    "percentage": 40.0
  },
  {
    "type": "SMB",
    "revenue": 3000.00,
    "percentage": 30.0
  },
  {
    "type": "Startup",
    "revenue": 2000.00,
    "percentage": 20.0
  },
  {
    "type": "Individual",
    "revenue": 1000.00,
    "percentage": 10.0
  }
]
```

**Business Logic**:
1. Get tenant_id from JWT
2. Determine date filter based on period:
   - month: invoice_date >= start of current month
   - quarter: invoice_date >= start of current quarter
   - year: invoice_date >= start of current financial year
   - all: no date filter
3. Query invoices:
   - JOIN with customers to get customer_id
   - JOIN with client_types to get type name
   - Filter by status = 'Paid'
   - Apply date filter
   - GROUP BY client_type
   - SUM revenue for each type
4. Calculate total revenue across all types
5. Calculate percentage for each type = (type_revenue / total_revenue) * 100
6. Sort by revenue descending
7. Return array of customer types with revenue and percentage

**Database Operations**:
```sql
SELECT
  ct.name as type,
  COALESCE(SUM(i.total), 0) as revenue
FROM invoices i
JOIN customers c ON i.customer_id = c.id
JOIN client_types ct ON c.client_type_id = ct.id
WHERE i.tenant_id = ?
  AND i.status = 'Paid'
  [AND i.invoice_date >= ?]  -- Date filter based on period
GROUP BY ct.name
ORDER BY revenue DESC
```

**Data Transformation**:
- Calculate percentages after fetching data
- Ensure percentages sum to 100% (handle rounding)

**Frontend Usage**:
- **File**: `src/pages/dashboard.tsx`
- **Component**: `CustomerChart` component
- **Called on**: Dashboard page load
- **Chart**: Pie chart showing revenue distribution

---

# 3. COMPANY PROFILE APIs

## 3.1 GET /api/v1/company

**Description**: Get company profile/settings for current tenant.

**Authentication**: Required

**Query Parameters**: None

**Success Response (200 OK)**:
```json
{
  "id": "uuid",
  "name": "Acme Corporation",
  "address": "123 Business Street, Mumbai, Maharashtra 400001",
  "registrationNumber": "CIN123456789",
  "taxId": "TAX123456",
  "contactName": "John Doe",
  "contactEmail": "john@acme.com",
  "contactPhone": "+91-9876543210",
  "financialYearStart": "2024-04-01",
  "currency": "INR",
  "industry": "Technology",
  "companySize": "51-200",
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-20T15:45:00Z"
}
```

**Error Responses**:
- `404 Not Found`: Company profile not created yet

**Business Logic**:
1. Get tenant_id from JWT
2. Query companies table WHERE tenant_id = ?
3. If found, return company details
4. If not found, return 404 (company not yet created)

**Database Operations**:
```sql
SELECT * FROM companies WHERE tenant_id = ? LIMIT 1
```

**Frontend Usage**:
- **File**: `src/pages/company.tsx`
- **Called on**: Page load
- **Purpose**: Pre-fill company form for editing

---

## 3.2 POST /api/v1/company

**Description**: Create or update company profile. If exists, updates; if not, creates new.

**Authentication**: Required (admin role)

**Request Body**:
```json
{
  "name": "Acme Corporation",
  "address": "123 Business Street, Mumbai, Maharashtra 400001",
  "registrationNumber": "CIN123456789",
  "taxId": "TAX123456",
  "contactName": "John Doe",
  "contactEmail": "john@acme.com",
  "contactPhone": "+91-9876543210",
  "financialYearStart": "2024-04-01",
  "currency": "INR",
  "industry": "Technology",
  "companySize": "51-200"
}
```

**Request Schema**:
| Field | Type | Required | Validation |
|-------|------|----------|------------|
| name | string | Yes | Min 2 chars, max 255 |
| address | string | Yes | Min 10 chars |
| registrationNumber | string | Yes | Not empty |
| taxId | string | Yes | Not empty |
| contactName | string | Yes | Min 2 chars |
| contactEmail | string | Yes | Valid email format |
| contactPhone | string | Yes | Min 10 chars |
| financialYearStart | date | Yes | Valid date, not in future |
| currency | string | Yes | Valid currency code (ISO 4217) |
| industry | string | Yes | From predefined list |
| companySize | string | Yes | From predefined list (1-10, 11-50, 51-200, 201-500, 501+) |

**Success Response (200 OK for update, 201 Created for new)**:
```json
{
  "id": "uuid",
  "name": "Acme Corporation",
  "address": "123 Business Street, Mumbai, Maharashtra 400001",
  "registrationNumber": "CIN123456789",
  "taxId": "TAX123456",
  "contactName": "John Doe",
  "contactEmail": "john@acme.com",
  "contactPhone": "+91-9876543210",
  "financialYearStart": "2024-04-01",
  "currency": "INR",
  "industry": "Technology",
  "companySize": "51-200",
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-20T15:45:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Validation errors
- `403 Forbidden`: User is not admin

**Business Logic**:
1. Verify user has admin role
2. Get tenant_id from JWT
3. Validate all fields
4. Check if company already exists for tenant
5. If exists:
   - UPDATE company record
   - Set updated_at = NOW()
   - Set created_by = current user_id
6. If not exists:
   - INSERT new company record
   - Set tenant_id
   - Set created_by = current user_id
   - Set created_at and updated_at
7. Return company details

**Database Operations**:
```sql
-- Check if exists
SELECT id FROM companies WHERE tenant_id = ? LIMIT 1

-- If exists, UPDATE
UPDATE companies SET
  name = ?, address = ?, registration_number = ?, tax_id = ?,
  contact_name = ?, contact_email = ?, contact_phone = ?,
  financial_year_start = ?, currency = ?, industry = ?, company_size = ?,
  updated_at = NOW(), created_by = ?
WHERE tenant_id = ?

-- If not exists, INSERT
INSERT INTO companies (id, tenant_id, name, address, ..., created_at, updated_at)
VALUES (?, ?, ?, ?, ..., NOW(), NOW())
```

**Side Effects**:
- Creates audit log entry
- May update tenant settings

**Frontend Usage**:
- **File**: `src/pages/company.tsx`
- **Called on**: Save button click
- **Purpose**: Save company configuration

---

# 4. CUSTOMER MANAGEMENT APIs

## 4.1 GET /api/v1/customers

**Description**: Get paginated list of customers with optional filtering and search.

**Authentication**: Required

**Query Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| search | string | No | - | Search in name, code, email |
| type | string | No | - | Filter by client type ID |
| isActive | boolean | No | - | Filter by active status |
| page | number | No | 1 | Page number |
| limit | number | No | 50 | Items per page (max 100) |
| sortBy | string | No | name | Field to sort by (name, code, createdAt) |
| sortOrder | string | No | asc | Sort direction (asc, desc) |

**Success Response (200 OK)**:
```json
{
  "data": [
    {
      "id": "uuid",
      "code": "CUST001",
      "name": "ABC Limited",
      "type": "Enterprise",
      "typeId": "uuid",
      "address": "456 Customer Lane, Delhi 110001",
      "email": "contact@abc.com",
      "whatsapp": "+91-9876543210",
      "phone": "+91-9876543210",
      "contactPerson": "Jane Smith",
      "gstNumber": "29ABCDE1234F1Z5",
      "panNumber": "ABCDE1234F",
      "paymentTerms": 30,
      "accountManager": "John Manager",
      "accountManagerId": "uuid",
      "isActive": true,
      "createdAt": "2024-01-15T10:30:00Z",
      "updatedAt": "2024-01-20T15:45:00Z"
    }
  ],
  "pagination": {
    "total": 150,
    "page": 1,
    "limit": 50,
    "totalPages": 3,
    "hasMore": true
  }
}
```

**Business Logic**:
1. Get tenant_id from JWT
2. Build query with filters:
   - Always filter by tenant_id
   - If search provided: WHERE (name LIKE %search% OR code LIKE %search% OR email LIKE %search%)
   - If type provided: AND client_type_id = type
   - If isActive provided: AND is_active = isActive
3. JOIN with client_types to get type name
4. JOIN with account_managers to get manager name
5. Apply sorting
6. Apply pagination (LIMIT, OFFSET)
7. Count total records for pagination
8. Calculate totalPages = CEIL(total / limit)
9. Return data and pagination metadata

**Database Operations**:
```sql
-- Count total
SELECT COUNT(*) as total FROM customers
WHERE tenant_id = ?
  [AND (name LIKE ? OR code LIKE ? OR email LIKE ?)]
  [AND client_type_id = ?]
  [AND is_active = ?]

-- Fetch data
SELECT
  c.*,
  ct.name as type,
  am.name as accountManager
FROM customers c
LEFT JOIN client_types ct ON c.client_type_id = ct.id
LEFT JOIN account_managers am ON c.account_manager_id = am.id
WHERE c.tenant_id = ?
  [AND (c.name LIKE ? OR c.code LIKE ? OR c.email LIKE ?)]
  [AND c.client_type_id = ?]
  [AND c.is_active = ?]
ORDER BY c.[sortBy] [sortOrder]
LIMIT ? OFFSET ?
```

**Frontend Usage**:
- **File**: `src/pages/customers/index.tsx`
- **Called on**: Page load, search input, filter change, pagination
- **Purpose**: Display customer list in data table

---

## 4.2 GET /api/v1/customers/:id

**Description**: Get single customer by ID with full details.

**Authentication**: Required

**Path Parameters**:
- `id` (uuid): Customer ID

**Success Response (200 OK)**:
```json
{
  "id": "uuid",
  "code": "CUST001",
  "name": "ABC Limited",
  "type": "Enterprise",
  "typeId": "uuid",
  "address": "456 Customer Lane, Delhi 110001",
  "email": "contact@abc.com",
  "whatsapp": "+91-9876543210",
  "phone": "+91-9876543210",
  "contactPerson": "Jane Smith",
  "gstNumber": "29ABCDE1234F1Z5",
  "panNumber": "ABCDE1234F",
  "paymentTerms": 30,
  "accountManager": "John Manager",
  "accountManagerId": "uuid",
  "isActive": true,
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-20T15:45:00Z"
}
```

**Error Responses**:
- `404 Not Found`: Customer not found or belongs to different tenant

**Business Logic**:
1. Get tenant_id from JWT
2. Query customer by ID AND tenant_id (ensure tenant isolation)
3. JOIN with client_types and account_managers
4. If found, return customer
5. If not found, return 404

**Database Operations**:
```sql
SELECT
  c.*,
  ct.name as type,
  am.name as accountManager
FROM customers c
LEFT JOIN client_types ct ON c.client_type_id = ct.id
LEFT JOIN account_managers am ON c.account_manager_id = am.id
WHERE c.id = ? AND c.tenant_id = ?
LIMIT 1
```

**Frontend Usage**:
- **File**: `src/pages/customers/create.tsx` (edit mode)
- **Called on**: Edit button click from customer list
- **Purpose**: Load customer data for editing

---

## 4.3 POST /api/v1/customers

**Description**: Create new customer.

**Authentication**: Required

**Request Body**:
```json
{
  "code": "CUST001",
  "name": "ABC Limited",
  "type": "uuid",
  "address": "456 Customer Lane, Delhi 110001",
  "email": "contact@abc.com",
  "whatsapp": "+91-9876543210",
  "phone": "+91-9876543210",
  "contactPerson": "Jane Smith",
  "gstNumber": "29ABCDE1234F1Z5",
  "panNumber": "ABCDE1234F",
  "paymentTerms": 30,
  "accountManager": "uuid",
  "isActive": true
}
```

**Request Schema**:
| Field | Type | Required | Validation |
|-------|------|----------|------------|
| code | string | Yes | Min 2 chars, unique within tenant |
| name | string | Yes | Min 2 chars |
| type | string (uuid) | Yes | Must exist in client_types |
| address | string | Yes | Min 10 chars |
| email | string | Yes | Valid email, unique within tenant |
| whatsapp | string | Yes | Min 10 chars |
| phone | string | Yes | Min 10 chars |
| contactPerson | string | Yes | Min 2 chars |
| gstNumber | string | No | Exactly 15 chars if provided (format: 29ABCDE1234F1Z5) |
| panNumber | string | No | Exactly 10 chars if provided (format: ABCDE1234F) |
| paymentTerms | number | Yes | Min 0 |
| accountManager | string (uuid) | Yes | Must exist in account_managers |
| isActive | boolean | No | Default true |

**Success Response (201 Created)**:
```json
{
  "id": "uuid",
  "code": "CUST001",
  "name": "ABC Limited",
  "type": "Enterprise",
  "typeId": "uuid",
  ...
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-15T10:30:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Validation errors
  ```json
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Validation failed",
      "details": {
        "code": "Customer code already exists",
        "gstNumber": "GST number must be exactly 15 characters"
      }
    }
  }
  ```
- `409 Conflict`: Code or email already exists

**Business Logic**:
1. Get tenant_id from JWT
2. Validate all fields
3. Check code uniqueness within tenant
4. Check email uniqueness within tenant
5. Verify client_type_id exists and belongs to tenant
6. Verify account_manager_id exists and belongs to tenant
7. Validate GST number format if provided (15 alphanumeric)
8. Validate PAN number format if provided (10 alphanumeric)
9. Generate UUID for customer
10. Set created_by = current user_id
11. Insert customer record
12. Increment tenant's customer count
13. Return created customer with joined data

**Database Operations**:
```sql
-- Check uniqueness
SELECT COUNT(*) FROM customers
WHERE tenant_id = ? AND (code = ? OR email = ?)

-- Verify foreign keys
SELECT id FROM client_types WHERE id = ? AND tenant_id = ?
SELECT id FROM account_managers WHERE id = ? AND tenant_id = ?

-- Insert
INSERT INTO customers (
  id, tenant_id, code, name, client_type_id, address, email,
  whatsapp, phone, contact_person, gst_number, pan_number,
  payment_terms, account_manager_id, is_active, created_by,
  created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW())

-- Update tenant count
UPDATE tenants SET current_customer_count = current_customer_count + 1
WHERE id = ?
```

**Validations**:
- GST Number: Regex `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$`
- PAN Number: Regex `^[A-Z]{5}[0-9]{4}[A-Z]{1}$`
- Email: Standard email regex
- Phone/WhatsApp: Minimum 10 characters (supports + and -)

**Side Effects**:
- Increments tenant customer count
- Creates audit log entry
- May check subscription limits (free tier: max 50 customers)

**Frontend Usage**:
- **File**: `src/pages/customers/create.tsx`
- **Called on**: Create button click
- **Purpose**: Add new customer to system

---

## 4.4 PUT /api/v1/customers/:id

**Description**: Update existing customer.

**Authentication**: Required

**Path Parameters**:
- `id` (uuid): Customer ID

**Request Body**: Same as POST /api/v1/customers

**Success Response (200 OK)**: Same as POST response

**Error Responses**: Same as POST

**Business Logic**:
1. Get tenant_id from JWT
2. Verify customer exists and belongs to tenant
3. Validate all fields (same as POST)
4. Check code uniqueness (excluding current customer)
5. Check email uniqueness (excluding current customer)
6. Verify foreign key references
7. Validate GST and PAN formats if provided
8. Update customer record
9. Set updated_at = NOW()
10. Return updated customer with joined data

**Database Operations**:
```sql
-- Verify exists
SELECT id FROM customers WHERE id = ? AND tenant_id = ?

-- Check uniqueness (excluding self)
SELECT COUNT(*) FROM customers
WHERE tenant_id = ? AND id != ? AND (code = ? OR email = ?)

-- Update
UPDATE customers SET
  code = ?, name = ?, client_type_id = ?, address = ?, email = ?,
  whatsapp = ?, phone = ?, contact_person = ?, gst_number = ?, pan_number = ?,
  payment_terms = ?, account_manager_id = ?, is_active = ?,
  updated_at = NOW()
WHERE id = ? AND tenant_id = ?
```

**Side Effects**:
- Creates audit log entry with old and new values
- May update related invoice customer names (denormalization)

**Frontend Usage**:
- **File**: `src/pages/customers/create.tsx` (edit mode)
- **Called on**: Update button click
- **Purpose**: Modify existing customer

---

## 4.5 DELETE /api/v1/customers/:id

**Description**: Delete customer. Uses soft delete if has invoices, hard delete otherwise.

**Authentication**: Required (admin role recommended)

**Path Parameters**:
- `id` (uuid): Customer ID

**Success Response (200 OK)**:
```json
{
  "success": true,
  "message": "Customer deleted successfully",
  "type": "soft"
}
```

**Error Responses**:
- `404 Not Found`: Customer not found
- `409 Conflict`: Cannot delete customer with pending invoices (optional strict mode)

**Business Logic**:
1. Get tenant_id from JWT
2. Verify customer exists and belongs to tenant
3. Check if customer has any invoices:
   - If has invoices: Soft delete (set is_active = false, deleted_at = NOW())
   - If no invoices: Hard delete (DELETE from table)
4. If soft delete, decrement tenant customer count
5. Return success with deletion type

**Database Operations**:
```sql
-- Check for invoices
SELECT COUNT(*) FROM invoices WHERE customer_id = ? AND tenant_id = ?

-- Soft delete
UPDATE customers SET is_active = false, deleted_at = NOW()
WHERE id = ? AND tenant_id = ?

-- Hard delete
DELETE FROM customers WHERE id = ? AND tenant_id = ?

-- Update count (if soft delete)
UPDATE tenants SET current_customer_count = current_customer_count - 1
WHERE id = ?
```

**Side Effects**:
- Decrements tenant customer count
- Creates audit log entry
- May orphan related records (invoices will still reference customer)

**Frontend Usage**:
- **File**: `src/pages/customers/index.tsx`
- **Called on**: Delete button confirmation
- **Purpose**: Remove customer from active list

---

# 5. SERVICE TYPE APIs

## 5.1 GET /api/v1/service-types

**Description**: Get list of all service types with optional filtering.

**Authentication**: Required

**Query Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| search | string | No | - | Search in name or code |
| isActive | boolean | No | - | Filter by active status |
| page | number | No | 1 | Page number |
| limit | number | No | 100 | Items per page |

**Success Response (200 OK)**:
```json
{
  "data": [
    {
      "id": "uuid",
      "code": "CONS",
      "name": "Consulting Services",
      "description": "Professional consulting services",
      "taxRate": 18.00,
      "isActive": true,
      "createdAt": "2024-01-15T10:30:00Z",
      "updatedAt": "2024-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "total": 25,
    "page": 1,
    "limit": 100,
    "totalPages": 1,
    "hasMore": false
  }
}
```

**Business Logic**:
1. Get tenant_id from JWT
2. Query service_types WHERE tenant_id = ?
3. Apply search filter if provided
4. Apply isActive filter if provided
5. Apply pagination
6. Return results

**Database Operations**:
```sql
SELECT * FROM service_types
WHERE tenant_id = ?
  [AND (name LIKE ? OR code LIKE ?)]
  [AND is_active = ?]
ORDER BY name ASC
LIMIT ? OFFSET ?
```

**Frontend Usage**:
- **File**: `src/pages/service-types.tsx`
- **File**: `src/pages/billing/create.tsx` (dropdown)
- **Called on**: Page load, invoice creation
- **Purpose**: Display/select service types

---

## 5.2 POST /api/v1/service-types

**Description**: Create new service type.

**Authentication**: Required

**Request Body**:
```json
{
  "code": "CONS",
  "name": "Consulting Services",
  "description": "Professional consulting services",
  "taxRate": 18.00,
  "isActive": true
}
```

**Request Schema**:
| Field | Type | Required | Validation |
|-------|------|----------|------------|
| code | string | Yes | Min 2 chars, unique within tenant |
| name | string | Yes | Min 2 chars, unique within tenant |
| description | string | Yes | Min 5 chars |
| taxRate | number | Yes | 0-100 (percentage) |
| isActive | boolean | No | Default true |

**Success Response (201 Created)**:
```json
{
  "id": "uuid",
  "code": "CONS",
  "name": "Consulting Services",
  "description": "Professional consulting services",
  "taxRate": 18.00,
  "isActive": true,
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-15T10:30:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Validation errors
- `409 Conflict`: Code or name already exists

**Business Logic**:
1. Get tenant_id from JWT
2. Validate all fields
3. Check code uniqueness within tenant
4. Check name uniqueness within tenant
5. Validate tax rate is between 0 and 100
6. Generate UUID
7. Insert service type
8. Return created service type

**Database Operations**:
```sql
-- Check uniqueness
SELECT COUNT(*) FROM service_types
WHERE tenant_id = ? AND (code = ? OR name = ?)

-- Insert
INSERT INTO service_types (
  id, tenant_id, code, name, description, tax_rate, is_active,
  created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, NOW(), NOW())
```

**Frontend Usage**:
- **File**: `src/pages/service-types.tsx`
- **Called on**: Create button in dialog
- **Purpose**: Add new billable service type

---

## 5.3 PUT /api/v1/service-types/:id

**Description**: Update service type.

**Authentication**: Required

**Path Parameters**:
- `id` (uuid): Service type ID

**Request Body**: Same as POST

**Success Response (200 OK)**: Same as POST response

**Business Logic**: Same as POST but for update

**Database Operations**:
```sql
UPDATE service_types SET
  code = ?, name = ?, description = ?, tax_rate = ?, is_active = ?,
  updated_at = NOW()
WHERE id = ? AND tenant_id = ?
```

**Frontend Usage**:
- **File**: `src/pages/service-types.tsx`
- **Called on**: Edit button in dialog
- **Purpose**: Modify service type

---

## 5.4 DELETE /api/v1/service-types/:id

**Description**: Delete service type (only if not used in invoices).

**Authentication**: Required

**Path Parameters**:
- `id` (uuid): Service type ID

**Success Response (200 OK)**:
```json
{
  "success": true,
  "message": "Service type deleted successfully"
}
```

**Error Responses**:
- `409 Conflict`: Service type is used in invoices

**Business Logic**:
1. Get tenant_id from JWT
2. Verify service type exists
3. Check if used in any invoice line items
4. If used, return 409 Conflict
5. If not used, DELETE
6. Return success

**Database Operations**:
```sql
-- Check usage
SELECT COUNT(*) FROM invoice_line_items
WHERE service_type_id = ? AND tenant_id = ?

-- Delete
DELETE FROM service_types WHERE id = ? AND tenant_id = ?
```

**Frontend Usage**:
- **File**: `src/pages/service-types.tsx`
- **Called on**: Delete confirmation
- **Purpose**: Remove unused service type

---

# 6. CLIENT TYPE APIs

## 6.1 GET /api/v1/client-types

**Description**: Get list of all client types.

**Authentication**: Required

**Query Parameters**: Same as service-types

**Success Response (200 OK)**:
```json
{
  "data": [
    {
      "id": "uuid",
      "code": "ENT",
      "name": "Enterprise",
      "description": "Large enterprise customers",
      "paymentTerms": 60,
      "isActive": true,
      "createdAt": "2024-01-15T10:30:00Z",
      "updatedAt": "2024-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "total": 10,
    "page": 1,
    "limit": 100,
    "totalPages": 1
  }
}
```

**Business Logic**: Similar to service-types

**Database Operations**:
```sql
SELECT * FROM client_types
WHERE tenant_id = ?
  [AND (name LIKE ? OR code LIKE ?)]
  [AND is_active = ?]
ORDER BY name ASC
LIMIT ? OFFSET ?
```

**Frontend Usage**:
- **File**: `src/pages/service-types.tsx` (Client Types tab)
- **File**: `src/pages/customers/create.tsx` (dropdown)
- **Called on**: Page load, customer creation
- **Purpose**: Display/select customer categories

---

## 6.2 POST /api/v1/client-types

**Description**: Create new client type.

**Authentication**: Required

**Request Body**:
```json
{
  "code": "ENT",
  "name": "Enterprise",
  "description": "Large enterprise customers",
  "paymentTerms": 60,
  "isActive": true
}
```

**Request Schema**:
| Field | Type | Required | Validation |
|-------|------|----------|------------|
| code | string | Yes | Min 2 chars, unique |
| name | string | Yes | Min 2 chars, unique |
| description | string | Yes | Min 5 chars |
| paymentTerms | number | Yes | >= 0 (days) |
| isActive | boolean | No | Default true |

**Success Response (201 Created)**: Similar structure

**Business Logic**: Similar to service-types

**Frontend Usage**:
- **File**: `src/pages/service-types.tsx`
- **Called on**: Create button
- **Purpose**: Add customer category

---

## 6.3 PUT /api/v1/client-types/:id

**Description**: Update client type.

**Path Parameters**: `id` (uuid)

**Request/Response**: Same as POST

**Frontend Usage**: Edit dialog

---

## 6.4 DELETE /api/v1/client-types/:id

**Description**: Delete client type (only if not used by customers).

**Path Parameters**: `id` (uuid)

**Business Logic**:
1. Check if type used by any customers
2. If used, return 409
3. If not used, DELETE

**Database Operations**:
```sql
SELECT COUNT(*) FROM customers WHERE client_type_id = ?
DELETE FROM client_types WHERE id = ? AND tenant_id = ?
```

**Frontend Usage**: Delete confirmation

---

# 7. ACCOUNT MANAGER APIs

## 7.1 GET /api/v1/account-managers

**Description**: Get list of all account managers.

**Authentication**: Required

**Query Parameters**:
| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| isActive | boolean | No | true |

**Success Response (200 OK)**:
```json
[
  {
    "id": "uuid",
    "name": "John Manager",
    "email": "john@company.com",
    "isActive": true
  }
]
```

**Business Logic**:
1. Get tenant_id from JWT
2. Query account_managers WHERE tenant_id = ?
3. Filter by isActive if specified
4. Return list (no pagination for simplicity)

**Database Operations**:
```sql
SELECT id, name, email, is_active
FROM account_managers
WHERE tenant_id = ? [AND is_active = ?]
ORDER BY name ASC
```

**Frontend Usage**:
- **File**: `src/pages/customers/create.tsx`
- **Called on**: Page load
- **Purpose**: Populate account manager dropdown

---

# 8. INVOICE MANAGEMENT APIs

## 8.1 GET /api/v1/invoices

**Description**: Get paginated list of invoices with filtering and search.

**Authentication**: Required

**Query Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| search | string | No | - | Search invoice number or customer name |
| status | string | No | - | Filter by status (Paid, Pending, Overdue) |
| customerId | string | No | - | Filter by customer ID |
| dateFrom | date | No | - | Invoice date >= |
| dateTo | date | No | - | Invoice date <= |
| page | number | No | 1 | Page number |
| limit | number | No | 50 | Items per page |
| sortBy | string | No | invoiceDate | Field to sort (invoiceNumber, invoiceDate, total) |
| sortOrder | string | No | desc | asc or desc |

**Success Response (200 OK)**:
```json
{
  "data": [
    {
      "id": "uuid",
      "invoiceNumber": "INV-2024-001",
      "invoiceDate": "2024-01-15",
      "customerId": "uuid",
      "customerName": "ABC Limited",
      "customerGst": "29ABCDE1234F1Z5",
      "dueDate": "2024-02-14",
      "referenceNumber": "PO-12345",
      "lineItems": [
        {
          "id": "uuid",
          "serviceType": "uuid",
          "serviceTypeName": "Consulting",
          "description": "Project consultation",
          "quantity": 10,
          "rate": 5000.00,
          "amount": 50000.00,
          "taxRate": 18.00,
          "taxAmount": 9000.00,
          "total": 59000.00
        }
      ],
      "subtotal": 50000.00,
      "taxTotal": 9000.00,
      "total": 59000.00,
      "status": "Pending",
      "notes": "Payment due within 30 days",
      "createdAt": "2024-01-15T10:30:00Z",
      "updatedAt": "2024-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "total": 250,
    "page": 1,
    "limit": 50,
    "totalPages": 5,
    "hasMore": true
  }
}
```

**Business Logic**:
1. Get tenant_id from JWT
2. Build query with filters
3. JOIN with customers for customer details
4. JOIN with invoice_line_items for line items
5. JOIN with service_types for service names
6. Calculate status dynamically:
   - "Paid": All payments allocated
   - "Overdue": due_date < current_date AND not paid
   - "Pending": due_date >= current_date AND not paid
7. Apply search, status, customer, date filters
8. Apply sorting and pagination
9. Return nested structure with line items

**Database Operations**:
```sql
-- Count total
SELECT COUNT(DISTINCT i.id) FROM invoices i
JOIN customers c ON i.customer_id = c.id
WHERE i.tenant_id = ?
  [AND (i.invoice_number LIKE ? OR c.name LIKE ?)]
  [AND i.status = ?]
  [AND i.customer_id = ?]
  [AND i.invoice_date >= ? AND i.invoice_date <= ?]

-- Fetch invoices
SELECT
  i.*,
  c.name as customerName,
  c.gst_number as customerGst
FROM invoices i
JOIN customers c ON i.customer_id = c.id
WHERE i.tenant_id = ?
  [filters...]
ORDER BY i.[sortBy] [sortOrder]
LIMIT ? OFFSET ?

-- For each invoice, fetch line items
SELECT
  li.*,
  st.name as serviceTypeName
FROM invoice_line_items li
LEFT JOIN service_types st ON li.service_type_id = st.id
WHERE li.invoice_id IN (?)
ORDER BY li.created_at ASC
```

**Status Calculation Logic**:
```javascript
if (invoice.payment_status === 'paid') {
  status = 'Paid';
} else if (new Date(invoice.due_date) < new Date()) {
  status = 'Overdue';
} else {
  status = 'Pending';
}
```

**Frontend Usage**:
- **File**: `src/pages/billing/index.tsx`
- **Component**: `DataTable` with columns
- **Called on**: Page load, search, filter, pagination
- **Purpose**: Display invoice list

---

## 8.2 GET /api/v1/invoices/:id

**Description**: Get single invoice by ID with full details including nested line items.

**Authentication**: Required

**Path Parameters**:
- `id` (uuid): Invoice ID

**Success Response (200 OK)**: Same as single invoice object from list endpoint

**Error Responses**:
- `404 Not Found`: Invoice not found or wrong tenant

**Business Logic**:
1. Get tenant_id from JWT
2. Query invoice by ID AND tenant_id
3. JOIN with customer
4. Fetch all line items with service type names
5. Return complete invoice object

**Database Operations**:
```sql
SELECT i.*, c.name as customerName, c.gst_number as customerGst
FROM invoices i
JOIN customers c ON i.customer_id = c.id
WHERE i.id = ? AND i.tenant_id = ?

SELECT li.*, st.name as serviceTypeName
FROM invoice_line_items li
LEFT JOIN service_types st ON li.service_type_id = st.id
WHERE li.invoice_id = ?
```

**Frontend Usage**:
- **File**: Invoice view/edit pages
- **Called on**: Edit button click, view details
- **Purpose**: Load full invoice data

---

## 8.3 POST /api/v1/invoices

**Description**: Create new invoice with line items.

**Authentication**: Required

**Request Body**:
```json
{
  "invoiceNumber": "INV-2024-001",
  "invoiceDate": "2024-01-15",
  "customerId": "uuid",
  "dueDate": "2024-02-14",
  "referenceNumber": "PO-12345",
  "lineItems": [
    {
      "serviceType": "uuid",
      "description": "Project consultation",
      "quantity": 10,
      "rate": 5000.00,
      "taxRate": 18.00
    }
  ],
  "notes": "Payment due within 30 days"
}
```

**Request Schema**:
| Field | Type | Required | Validation |
|-------|------|----------|------------|
| invoiceNumber | string | Yes | Unique within tenant, or auto-generated |
| invoiceDate | date | Yes | Valid date |
| customerId | string (uuid) | Yes | Must exist, belong to tenant |
| dueDate | date | Yes | >= invoiceDate |
| referenceNumber | string | No | Max 100 chars |
| lineItems | array | Yes | Min 1 item |
| lineItems[].serviceType | string (uuid) | Yes | Must exist |
| lineItems[].description | string | No | Max 500 chars |
| lineItems[].quantity | number | Yes | Min 1 |
| lineItems[].rate | number | Yes | Min 0 |
| lineItems[].taxRate | number | Yes | 0-100 |
| notes | string | No | Max 1000 chars |

**Success Response (201 Created)**:
```json
{
  "id": "uuid",
  "invoiceNumber": "INV-2024-001",
  ...
  "subtotal": 50000.00,
  "taxTotal": 9000.00,
  "total": 59000.00,
  "status": "Pending",
  "createdAt": "2024-01-15T10:30:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Validation errors
- `409 Conflict`: Invoice number exists
- `402 Payment Required`: Trial expired or invoice limit reached

**Business Logic**:
1. Get tenant_id and user_id from JWT
2. **Check subscription limits**:
   - If on trial or free tier, check invoice count
   - If limit reached, return 402 Payment Required
3. Validate all fields
4. Verify customer exists and belongs to tenant
5. Verify all service types exist and belong to tenant
6. Validate due date >= invoice date
7. Check invoice number uniqueness (or auto-generate if not provided)
8. **Calculate line item amounts**:
   - For each line item:
     - amount = quantity × rate
     - taxAmount = amount × (taxRate / 100)
     - total = amount + taxAmount
9. **Calculate invoice totals**:
   - subtotal = SUM(line_items.amount)
   - taxTotal = SUM(line_items.taxAmount)
   - total = subtotal + taxTotal
10. Set initial status based on due date:
    - If due_date >= current_date: "Pending"
    - If due_date < current_date: "Overdue"
11. Insert invoice record
12. Insert line items (with foreign key to invoice)
13. Increment tenant invoice count
14. Return created invoice with all details

**Calculation Formulas**:
```javascript
// Line item calculations
lineItem.amount = lineItem.quantity * lineItem.rate;
lineItem.taxAmount = lineItem.amount * (lineItem.taxRate / 100);
lineItem.total = lineItem.amount + lineItem.taxAmount;

// Invoice calculations
invoice.subtotal = sum(lineItems.map(li => li.amount));
invoice.taxTotal = sum(lineItems.map(li => li.taxAmount));
invoice.total = invoice.subtotal + invoice.taxTotal;
```

**Database Operations**:
```sql
-- Check subscription limit
SELECT current_invoice_count, subscription_status FROM tenants WHERE id = ?

-- Check uniqueness
SELECT COUNT(*) FROM invoices
WHERE tenant_id = ? AND invoice_number = ?

-- Verify customer
SELECT id FROM customers WHERE id = ? AND tenant_id = ?

-- Verify service types
SELECT id FROM service_types WHERE id IN (?) AND tenant_id = ?

-- Insert invoice
INSERT INTO invoices (
  id, tenant_id, invoice_number, invoice_date, customer_id, due_date,
  reference_number, subtotal, tax_total, total, status, notes,
  created_by, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW())

-- Insert line items
INSERT INTO invoice_line_items (
  id, tenant_id, invoice_id, service_type_id, description,
  quantity, rate, amount, tax_rate, tax_amount, total,
  created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW())
-- Repeat for each line item

-- Update tenant count
UPDATE tenants SET current_invoice_count = current_invoice_count + 1
WHERE id = ?
```

**Side Effects**:
- Increments tenant invoice count
- Creates audit log entry
- May send invoice email to customer (optional)
- May trigger notification to account manager

**Frontend Usage**:
- **File**: `src/pages/billing/create.tsx`
- **File**: `src/components/billing/create-invoice-modal.tsx`
- **Called on**: Save/Create button click
- **Purpose**: Create new invoice

---

## 8.4 PUT /api/v1/invoices/:id

**Description**: Update existing invoice (only if status is Pending or Draft).

**Authentication**: Required

**Path Parameters**:
- `id` (uuid): Invoice ID

**Request Body**: Same as POST

**Success Response (200 OK)**: Same as created invoice

**Error Responses**:
- `400 Bad Request`: Validation errors
- `403 Forbidden`: Cannot edit paid invoices
- `404 Not Found`: Invoice not found

**Business Logic**:
1. Get tenant_id from JWT
2. Verify invoice exists and belongs to tenant
3. **Check if invoice can be edited**:
   - If status = "Paid", return 403 Forbidden
   - If has receipts allocated, return 403 Forbidden
4. Validate all fields (same as POST)
5. **Delete existing line items**
6. **Insert new line items** with recalculated amounts
7. **Recalculate invoice totals**
8. Update invoice record
9. Set updated_at = NOW()
10. Return updated invoice

**Database Operations**:
```sql
-- Check status
SELECT id, status FROM invoices
WHERE id = ? AND tenant_id = ?

-- Check for payments
SELECT COUNT(*) FROM receipt_allocations
WHERE invoice_id = ?

-- Delete old line items
DELETE FROM invoice_line_items WHERE invoice_id = ?

-- Insert new line items (same as POST)
-- Update invoice (same calculations as POST)
UPDATE invoices SET
  invoice_number = ?, invoice_date = ?, customer_id = ?,
  due_date = ?, reference_number = ?, subtotal = ?, tax_total = ?,
  total = ?, notes = ?, updated_at = NOW()
WHERE id = ? AND tenant_id = ?
```

**Side Effects**:
- Creates audit log with old and new values
- May trigger email notification of invoice update

**Frontend Usage**:
- **File**: `src/pages/billing/create.tsx` (edit mode)
- **Called on**: Update button click
- **Purpose**: Modify unpaid invoices

---

## 8.5 DELETE /api/v1/invoices/:id

**Description**: Delete invoice (only if no payments received).

**Authentication**: Required (admin role recommended)

**Path Parameters**:
- `id` (uuid): Invoice ID

**Success Response (200 OK)**:
```json
{
  "success": true,
  "message": "Invoice deleted successfully"
}
```

**Error Responses**:
- `403 Forbidden`: Cannot delete paid invoices or invoices with receipts
- `404 Not Found`: Invoice not found

**Business Logic**:
1. Get tenant_id from JWT
2. Verify invoice exists
3. Check for receipt allocations:
   - If has payments, return 403 Forbidden
4. Check for credit notes:
   - If has credit notes, return 403 Forbidden
5. **Delete line items first** (foreign key constraint)
6. **Delete invoice**
7. Decrement tenant invoice count
8. Return success

**Database Operations**:
```sql
-- Check for receipts
SELECT COUNT(*) FROM receipt_allocations WHERE invoice_id = ?

-- Check for credit notes
SELECT COUNT(*) FROM credit_notes WHERE invoice_id = ?

-- Delete line items
DELETE FROM invoice_line_items WHERE invoice_id = ?

-- Delete invoice
DELETE FROM invoices WHERE id = ? AND tenant_id = ?

-- Update count
UPDATE tenants SET current_invoice_count = current_invoice_count - 1
WHERE id = ?
```

**Side Effects**:
- Decrements tenant invoice count
- Creates audit log entry

**Frontend Usage**:
- **File**: `src/pages/billing/index.tsx`
- **Called on**: Delete button confirmation
- **Purpose**: Remove invoice

---

## 8.6 GET /api/v1/invoices/:id/pdf

**Description**: Generate and download invoice PDF.

**Authentication**: Required

**Path Parameters**:
- `id` (uuid): Invoice ID

**Success Response (200 OK)**:
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename="INV-2024-001.pdf"`
- Body: PDF binary data

**Error Responses**:
- `404 Not Found`: Invoice not found

**Business Logic**:
1. Get tenant_id from JWT
2. Fetch invoice with all details
3. Fetch company information
4. Fetch customer information
5. **Generate PDF** with:
   - Company logo and details
   - Invoice number, date, due date
   - Customer details
   - Line items table
   - Subtotal, tax breakdown, total
   - Payment terms and notes
   - GST details if applicable
6. Set appropriate headers
7. Stream PDF to client

**PDF Template Structure**:
```
[Company Logo]          INVOICE
Company Name            Invoice #: INV-2024-001
Address                 Date: 15 Jan 2024
GST: XX...              Due Date: 14 Feb 2024

BILL TO:
Customer Name
Address
GST: XX...

DESCRIPTION                   QTY    RATE      AMOUNT     TAX    TOTAL
Consulting Services           10     5000      50000      9000   59000

                                            SUBTOTAL:    50000.00
                                            TAX (18%):    9000.00
                                            TOTAL:       59000.00

Notes: Payment due within 30 days

Payment Terms:
[Payment details]
```

**Frontend Usage**:
- **File**: Invoice view page, invoice list
- **Called on**: Download PDF button click
- **Purpose**: Generate invoice PDF for printing/emailing

---

## 8.7 POST /api/v1/invoices/:id/send-email

**Description**: Email invoice PDF to customer.

**Authentication**: Required

**Path Parameters**:
- `id` (uuid): Invoice ID

**Request Body**:
```json
{
  "to": "customer@example.com",
  "cc": ["manager@company.com"],
  "subject": "Invoice INV-2024-001",
  "message": "Dear Customer, Please find attached invoice...",
  "includePaymentLink": false
}
```

**Success Response (200 OK)**:
```json
{
  "success": true,
  "message": "Invoice emailed successfully",
  "sentTo": "customer@example.com",
  "sentAt": "2024-01-15T10:30:00Z"
}
```

**Error Responses**:
- `404 Not Found`: Invoice not found
- `500 Internal Server Error`: Email sending failed

**Business Logic**:
1. Verify invoice exists
2. Generate PDF (same as GET /pdf)
3. Get customer email (default if not provided)
4. Prepare email:
   - Subject: custom or default
   - Body: custom message or template
   - Attach PDF
5. Send email via SMTP
6. Log email sent event
7. Return success

**Side Effects**:
- Sends email
- Creates audit log entry
- May update invoice.last_emailed_at field

**Frontend Usage**:
- **File**: Invoice view page
- **Called on**: Send Email button click
- **Purpose**: Email invoice to customer

---

# 9. RECEIPT (PAYMENT) APIs

## 9.1 GET /api/v1/receipts

**Description**: Get list of all payment receipts.

**Authentication**: Required

**Query Parameters**:
| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| search | string | No | - |
| customerId | string | No | - |
| paymentMethod | string | No | - |
| dateFrom | date | No | - |
| dateTo | date | No | - |
| page | number | No | 1 |
| limit | number | No | 50 |

**Success Response (200 OK)**:
```json
{
  "data": [
    {
      "id": "uuid",
      "receiptId": "RCT-2024-001",
      "receiptDate": "2024-01-20",
      "customerId": "uuid",
      "customerName": "ABC Limited",
      "paymentMethod": "Bank Transfer",
      "amountReceived": 59000.00,
      "allocations": [
        {
          "invoiceId": "uuid",
          "invoiceNumber": "INV-2024-001",
          "amountAllocated": 59000.00
        }
      ],
      "totalAllocated": 59000.00,
      "unappliedAmount": 0.00,
      "notes": "",
      "status": "Completed",
      "createdAt": "2024-01-20T14:30:00Z"
    }
  ],
  "pagination": {
    "total": 100,
    "page": 1,
    "limit": 50,
    "totalPages": 2
  }
}
```

**Business Logic**:
1. Get tenant_id from JWT
2. Query receipts with JOINs
3. JOIN with customers
4. JOIN with receipt_allocations
5. JOIN with invoices for invoice numbers
6. Apply filters
7. Calculate totals
8. Apply pagination

**Database Operations**:
```sql
SELECT
  r.*,
  c.name as customerName
FROM receipts r
JOIN customers c ON r.customer_id = c.id
WHERE r.tenant_id = ?
  [AND (r.receipt_id LIKE ? OR c.name LIKE ?)]
  [AND r.customer_id = ?]
  [AND r.payment_method = ?]
  [AND r.receipt_date >= ? AND r.receipt_date <= ?]
ORDER BY r.receipt_date DESC
LIMIT ? OFFSET ?

-- For each receipt, get allocations
SELECT
  ra.*,
  i.invoice_number
FROM receipt_allocations ra
JOIN invoices i ON ra.invoice_id = i.id
WHERE ra.receipt_id IN (?)
```

**Frontend Usage**:
- **File**: `src/pages/receipts/index.tsx`
- **Called on**: Page load, filters
- **Purpose**: Display payment history

---

## 9.2 GET /api/v1/receipts/:id

**Description**: Get single receipt by ID.

**Authentication**: Required

**Path Parameters**:
- `id` (uuid): Receipt ID

**Success Response (200 OK)**: Single receipt object

**Frontend Usage**: Receipt view/print

---

## 9.3 POST /api/v1/receipts

**Description**: Record a payment receipt and allocate to invoices.

**Authentication**: Required

**Request Body**:
```json
{
  "receiptId": "RCT-2024-001",
  "receiptDate": "2024-01-20",
  "customerId": "uuid",
  "paymentMethod": "Bank Transfer",
  "amountReceived": 59000.00,
  "allocations": [
    {
      "invoiceId": "uuid",
      "amountAllocated": 59000.00
    }
  ],
  "notes": ""
}
```

**Request Schema**:
| Field | Type | Required | Validation |
|-------|------|----------|------------|
| receiptId | string | Yes | Unique within tenant, or auto-generated |
| receiptDate | date | Yes | Valid date, not in future |
| customerId | string (uuid) | Yes | Must exist |
| paymentMethod | string | Yes | bank_transfer, cheque, cash, upi, card |
| amountReceived | number | Yes | Min 1 |
| allocations | array | Yes | Min 1 allocation |
| allocations[].invoiceId | string (uuid) | Yes | Must exist, belong to customer |
| allocations[].amountAllocated | number | Yes | Min 0.01, <= invoice outstanding |
| notes | string | No | Max 1000 chars |

**Success Response (201 Created)**:
```json
{
  "id": "uuid",
  "receiptId": "RCT-2024-001",
  "receiptDate": "2024-01-20",
  ...
  "totalAllocated": 59000.00,
  "unappliedAmount": 0.00,
  "status": "Completed",
  "invoicesUpdated": ["INV-2024-001"],
  "createdAt": "2024-01-20T14:30:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Validation errors, allocation exceeds invoice amount
- `409 Conflict`: Receipt ID exists

**Business Logic**:
1. Get tenant_id and user_id from JWT
2. Validate all fields
3. Verify customer exists
4. Verify all invoices:
   - Exist and belong to tenant
   - Belong to the specified customer
   - Are not already fully paid
5. **Validate allocations**:
   - Each allocation amount <= invoice outstanding amount
   - SUM(allocations) <= amountReceived
6. Check receipt ID uniqueness (or auto-generate)
7. **Calculate unapplied amount** = amountReceived - SUM(allocations)
8. Insert receipt record
9. **Insert allocation records** for each invoice
10. **For each allocated invoice**:
    - Calculate new outstanding = invoice.total - SUM(all allocations for this invoice)
    - If outstanding <= 0:
      - Update invoice.status = 'Paid'
      - Set invoice.payment_date = receipt_date
    - Else if partially paid:
      - Update invoice.status = 'Partially Paid'
11. Return created receipt with invoices updated

**Calculations**:
```javascript
totalAllocated = sum(allocations.map(a => a.amountAllocated));
unappliedAmount = amountReceived - totalAllocated;

// For each invoice
invoice.outstandingAmount = invoice.total - sum(all_allocations);
if (invoice.outstandingAmount <= 0) {
  invoice.status = 'Paid';
  invoice.payment_date = receipt.receiptDate;
}
```

**Database Operations**:
```sql
-- Verify customer
SELECT id FROM customers WHERE id = ? AND tenant_id = ?

-- Verify invoices belong to customer
SELECT id, invoice_number, total FROM invoices
WHERE id IN (?) AND customer_id = ? AND tenant_id = ?

-- Get existing allocations for invoices
SELECT invoice_id, SUM(allocated_amount) as total_allocated
FROM receipt_allocations
WHERE invoice_id IN (?)
GROUP BY invoice_id

-- Insert receipt
INSERT INTO receipts (
  id, tenant_id, receipt_number, receipt_date, customer_id,
  payment_method, amount, status, notes, created_by,
  created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW())

-- Insert allocations
INSERT INTO receipt_allocations (
  id, tenant_id, receipt_id, invoice_id, allocated_amount,
  created_at, updated_at
) VALUES (?, ?, ?, ?, ?, NOW(), NOW())
-- Repeat for each allocation

-- Update invoice status
UPDATE invoices SET
  status = 'Paid',
  payment_date = ?
WHERE id IN (?) AND tenant_id = ?
```

**Side Effects**:
- Updates invoice status to Paid
- Sets invoice payment_date
- Creates audit log entries
- May send payment confirmation email to customer
- Updates dashboard metrics

**Frontend Usage**:
- **File**: `src/components/billing/create-receipt-modal.tsx`
- **Called on**: Record Payment button click
- **Purpose**: Record customer payments against invoices

---

# 10. CREDIT NOTE APIs

## 10.1 GET /api/v1/credit-notes

**Description**: Get list of all credit notes.

**Authentication**: Required

**Query Parameters**:
| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| search | string | No | - |
| customerId | string | No | - |
| invoiceId | string | No | - |
| reason | string | No | - |
| dateFrom | date | No | - |
| dateTo | date | No | - |
| page | number | No | 1 |
| limit | number | No | 50 |

**Success Response (200 OK)**:
```json
{
  "data": [
    {
      "id": "uuid",
      "creditNoteId": "CN-2024-001",
      "creditNoteDate": "2024-01-25",
      "customerId": "uuid",
      "customerName": "ABC Limited",
      "invoiceId": "uuid",
      "invoiceNumber": "INV-2024-001",
      "reason": "Service not delivered",
      "amount": 10000.00,
      "gstRate": 18.00,
      "gstAmount": 1800.00,
      "totalCredit": 11800.00,
      "status": "Issued",
      "notes": "",
      "createdAt": "2024-01-25T16:00:00Z"
    }
  ],
  "pagination": {
    "total": 50,
    "page": 1,
    "limit": 50,
    "totalPages": 1
  }
}
```

**Business Logic**:
1. Query credit_notes with JOINs
2. JOIN with customers and invoices
3. Apply filters
4. Apply pagination

**Database Operations**:
```sql
SELECT
  cn.*,
  c.name as customerName,
  i.invoice_number as invoiceNumber
FROM credit_notes cn
JOIN customers c ON cn.customer_id = c.id
LEFT JOIN invoices i ON cn.invoice_id = i.id
WHERE cn.tenant_id = ?
  [filters...]
ORDER BY cn.credit_note_date DESC
LIMIT ? OFFSET ?
```

**Frontend Usage**:
- **File**: `src/pages/credit-notes/index.tsx`
- **Called on**: Page load
- **Purpose**: Display credit note list

---

## 10.2 GET /api/v1/credit-notes/:id

**Description**: Get single credit note by ID.

**Authentication**: Required

**Path Parameters**:
- `id` (uuid): Credit note ID

**Success Response (200 OK)**: Single credit note object

**Frontend Usage**: Credit note view/print

---

## 10.3 POST /api/v1/credit-notes

**Description**: Issue a credit note (refund/adjustment).

**Authentication**: Required

**Request Body**:
```json
{
  "creditNoteId": "CN-2024-001",
  "creditNoteDate": "2024-01-25",
  "customerId": "uuid",
  "invoiceId": "uuid",
  "reason": "Service not delivered",
  "amount": 10000.00,
  "gstRate": 18.00,
  "notes": ""
}
```

**Request Schema**:
| Field | Type | Required | Validation |
|-------|------|----------|------------|
| creditNoteId | string | Yes | Unique, or auto-generated |
| creditNoteDate | date | Yes | Valid date |
| customerId | string (uuid) | Yes | Must exist |
| invoiceId | string (uuid) | No | Must exist, belong to customer |
| reason | string | Yes | From predefined list or free text |
| amount | number | Yes | Min 1, <= invoice total if invoice linked |
| gstRate | number | Yes | 0-100 |
| notes | string | No | Max 1000 chars |

**Success Response (201 Created)**:
```json
{
  "id": "uuid",
  "creditNoteId": "CN-2024-001",
  "creditNoteDate": "2024-01-25",
  ...
  "gstAmount": 1800.00,
  "totalCredit": 11800.00,
  "status": "Issued",
  "createdAt": "2024-01-25T16:00:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Validation errors, credit exceeds invoice
- `409 Conflict`: Credit note ID exists

**Business Logic**:
1. Get tenant_id from JWT
2. Validate all fields
3. Verify customer exists
4. If invoice provided:
   - Verify invoice exists and belongs to customer
   - Verify invoice is paid (typically)
   - Verify total credits for invoice don't exceed invoice amount
5. Check credit note ID uniqueness (or auto-generate)
6. **Calculate GST amount** = amount × (gstRate / 100)
7. **Calculate total credit** = amount + gstAmount
8. Insert credit note record
9. Set status = 'Issued'
10. May create accounting entry
11. Return created credit note

**Calculations**:
```javascript
gstAmount = amount * (gstRate / 100);
totalCredit = amount + gstAmount;
```

**Database Operations**:
```sql
-- Verify customer and invoice
SELECT id FROM customers WHERE id = ? AND tenant_id = ?
SELECT id, total FROM invoices
WHERE id = ? AND customer_id = ? AND tenant_id = ?

-- Check existing credits for invoice
SELECT SUM(total_credit) FROM credit_notes
WHERE invoice_id = ? AND status != 'Cancelled'

-- Insert credit note
INSERT INTO credit_notes (
  id, tenant_id, credit_note_number, credit_note_date,
  customer_id, invoice_id, reason, amount, gst_amount,
  total_credit, status, notes, created_by,
  created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW())
```

**Side Effects**:
- Creates audit log entry
- May send credit note email to customer
- May update accounting ledgers

**Frontend Usage**:
- **File**: `src/components/credit-notes/create-credit-note-modal.tsx`
- **Called on**: Issue Credit Note button
- **Purpose**: Issue refunds or adjustments

---

# 11. GST SETTINGS APIs

## 11.1 GET /api/v1/gst-settings

**Description**: Get GST/tax configuration for current tenant.

**Authentication**: Required

**Query Parameters**: None

**Success Response (200 OK)**:
```json
{
  "id": "uuid",
  "isGstApplicable": true,
  "gstNumber": "29ABCDE1234F1Z5",
  "effectiveDate": "2024-01-01",
  "defaultRate": 18.00,
  "displayFormat": "Exclusive",
  "filingFrequency": "MONTHLY",
  "taxRates": [
    {
      "id": "uuid",
      "category": "Services",
      "rate": 18.00,
      "effectiveFrom": "2024-01-01",
      "description": "Standard GST rate for services"
    },
    {
      "id": "uuid",
      "category": "Products",
      "rate": 12.00,
      "effectiveFrom": "2024-01-01",
      "description": "Reduced GST rate for products"
    }
  ],
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-15T10:30:00Z"
}
```

**Error Responses**:
- `404 Not Found`: GST settings not configured yet

**Business Logic**:
1. Get tenant_id from JWT
2. Query gst_settings WHERE tenant_id = ?
3. Include nested tax_rates
4. Return settings

**Database Operations**:
```sql
SELECT * FROM gst_settings WHERE tenant_id = ? LIMIT 1

SELECT * FROM tax_rates
WHERE gst_setting_id = ? OR tenant_id = ?
ORDER BY category, effective_from DESC
```

**Frontend Usage**:
- **File**: `src/pages/gst.tsx`
- **Called on**: Page load
- **Purpose**: Load GST configuration for editing

---

## 11.2 POST /api/v1/gst-settings

**Description**: Create or update GST settings with tax rates.

**Authentication**: Required (admin role)

**Request Body**:
```json
{
  "isGstApplicable": true,
  "gstNumber": "29ABCDE1234F1Z5",
  "effectiveDate": "2024-01-01",
  "defaultRate": 18.00,
  "displayFormat": "Exclusive",
  "filingFrequency": "MONTHLY",
  "taxRates": [
    {
      "category": "Services",
      "rate": 18.00,
      "effectiveFrom": "2024-01-01",
      "description": "Standard GST rate for services"
    }
  ]
}
```

**Request Schema**:
| Field | Type | Required | Validation |
|-------|------|----------|------------|
| isGstApplicable | boolean | Yes | - |
| gstNumber | string | Conditional | Required if isGstApplicable=true, exactly 15 chars |
| effectiveDate | date | Yes | Valid date |
| defaultRate | number | Yes | 0-100 |
| displayFormat | string | Yes | Inclusive or Exclusive |
| filingFrequency | string | Yes | MONTHLY, QUARTERLY, ANNUALLY |
| taxRates | array | No | Each rate 0-100 |

**Success Response (200 OK for update, 201 Created for new)**:
```json
{
  "id": "uuid",
  "isGstApplicable": true,
  ...
  "taxRates": [...],
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-20T11:00:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Validation errors
- `403 Forbidden`: User not admin

**Business Logic**:
1. Verify user has admin role
2. Get tenant_id from JWT
3. Validate all fields
4. If isGstApplicable = true, validate gstNumber format
5. Validate filing frequency is one of allowed values
6. Validate all tax rates are 0-100
7. Check if settings exist:
   - If exists: UPDATE settings
   - If not: INSERT settings
8. **Delete existing tax rates** for this tenant
9. **Insert new tax rates** with references to settings
10. Return complete settings with tax rates

**Database Operations**:
```sql
-- Check if exists
SELECT id FROM gst_settings WHERE tenant_id = ? LIMIT 1

-- Update or Insert settings
UPDATE gst_settings SET
  is_gst_applicable = ?, gst_number = ?, effective_date = ?,
  default_rate = ?, display_format = ?, filing_frequency = ?,
  updated_at = NOW()
WHERE tenant_id = ?
-- OR
INSERT INTO gst_settings (...) VALUES (...)

-- Delete old tax rates
DELETE FROM tax_rates WHERE tenant_id = ?

-- Insert new tax rates
INSERT INTO tax_rates (
  id, tenant_id, gst_setting_id, category, rate,
  effective_from, description, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, NOW(), NOW())
-- Repeat for each rate
```

**Side Effects**:
- Creates audit log entry
- May affect invoice tax calculations going forward

**Frontend Usage**:
- **File**: `src/pages/gst.tsx`
- **Called on**: Save Changes button
- **Purpose**: Configure GST settings

---

# 12. HELPER/UTILITY APIs

## 12.1 GET /api/v1/invoices/next-number

**Description**: Get next available invoice number for auto-generation.

**Authentication**: Required

**Query Parameters**: None

**Success Response (200 OK)**:
```json
{
  "nextNumber": "INV-2024-123",
  "pattern": "INV-YYYY-###",
  "year": 2024,
  "sequence": 123
}
```

**Business Logic**:
1. Get tenant_id from JWT
2. Get current year (YYYY)
3. Find highest invoice number for current year:
   - Query: SELECT MAX(invoice_number) WHERE invoice_number LIKE 'INV-2024-%'
   - Extract sequence number (rightmost ###)
4. Increment sequence by 1
5. Format as INV-YYYY-###
6. Return next number

**Database Operations**:
```sql
SELECT invoice_number FROM invoices
WHERE tenant_id = ? AND invoice_number LIKE ?
ORDER BY invoice_number DESC
LIMIT 1
```

**Frontend Usage**:
- **File**: `src/pages/billing/create.tsx`
- **Called on**: Page load, auto-populate field
- **Purpose**: Auto-generate invoice numbers

---

## 12.2 GET /api/v1/receipts/next-number

**Description**: Get next available receipt number.

**Authentication**: Required

**Success Response (200 OK)**:
```json
{
  "nextNumber": "RCT-2024-045",
  "pattern": "RCT-YYYY-###"
}
```

**Business Logic**: Same as invoices but for receipts (RCT-YYYY-###)

**Frontend Usage**:
- **File**: `src/components/billing/create-receipt-modal.tsx`
- **Called on**: Modal open
- **Purpose**: Auto-generate receipt numbers

---

## 12.3 GET /api/v1/credit-notes/next-number

**Description**: Get next available credit note number.

**Authentication**: Required

**Success Response (200 OK)**:
```json
{
  "nextNumber": "CN-2024-012",
  "pattern": "CN-YYYY-###"
}
```

**Business Logic**: Same as invoices but for credit notes (CN-YYYY-###)

**Frontend Usage**:
- **File**: `src/components/credit-notes/create-credit-note-modal.tsx`
- **Called on**: Modal open
- **Purpose**: Auto-generate credit note numbers

---

## 12.4 GET /api/v1/customers/:customerId/pending-invoices

**Description**: Get all unpaid invoices for a specific customer (for payment allocation).

**Authentication**: Required

**Path Parameters**:
- `customerId` (uuid): Customer ID

**Success Response (200 OK)**:
```json
[
  {
    "id": "uuid",
    "invoiceNumber": "INV-2024-001",
    "invoiceDate": "2024-01-15",
    "dueDate": "2024-02-14",
    "total": 59000.00,
    "paidAmount": 0.00,
    "outstandingAmount": 59000.00,
    "status": "Pending"
  }
]
```

**Business Logic**:
1. Get tenant_id from JWT
2. Verify customer belongs to tenant
3. Query invoices WHERE:
   - customer_id = customerId
   - status IN ('Pending', 'Overdue', 'Partially Paid')
   - tenant_id = current tenant
4. For each invoice:
   - Calculate paidAmount = SUM(receipt allocations)
   - Calculate outstandingAmount = total - paidAmount
5. Return only invoices with outstandingAmount > 0
6. Sort by invoice_date ASC (oldest first)

**Database Operations**:
```sql
SELECT
  i.id, i.invoice_number, i.invoice_date, i.due_date, i.total,
  COALESCE(SUM(ra.allocated_amount), 0) as paid_amount,
  i.total - COALESCE(SUM(ra.allocated_amount), 0) as outstanding_amount
FROM invoices i
LEFT JOIN receipt_allocations ra ON i.id = ra.invoice_id
WHERE i.customer_id = ?
  AND i.tenant_id = ?
  AND i.status IN ('Pending', 'Overdue', 'Partially Paid')
GROUP BY i.id
HAVING outstanding_amount > 0
ORDER BY i.invoice_date ASC
```

**Frontend Usage**:
- **File**: `src/components/billing/create-receipt-modal.tsx`
- **Called on**: Customer selected in receipt form
- **Purpose**: Show invoices available for payment allocation

---

## 12.5 GET /api/v1/customers/:customerId/paid-invoices

**Description**: Get all paid invoices for a customer (for credit note issuance).

**Authentication**: Required

**Path Parameters**:
- `customerId` (uuid): Customer ID

**Success Response (200 OK)**:
```json
[
  {
    "id": "uuid",
    "invoiceNumber": "INV-2024-001",
    "invoiceDate": "2024-01-15",
    "total": 59000.00,
    "creditNotesIssued": 11800.00,
    "availableForCredit": 47200.00
  }
]
```

**Business Logic**:
1. Get tenant_id from JWT
2. Query invoices WHERE:
   - customer_id = customerId
   - status = 'Paid'
   - tenant_id = current tenant
3. For each invoice:
   - Calculate creditNotesIssued = SUM(credit notes for this invoice)
   - Calculate availableForCredit = total - creditNotesIssued
4. Return only invoices with availableForCredit > 0
5. Sort by invoice_date DESC (recent first)

**Database Operations**:
```sql
SELECT
  i.id, i.invoice_number, i.invoice_date, i.total,
  COALESCE(SUM(cn.total_credit), 0) as credit_notes_issued,
  i.total - COALESCE(SUM(cn.total_credit), 0) as available_for_credit
FROM invoices i
LEFT JOIN credit_notes cn ON i.id = cn.invoice_id AND cn.status != 'Cancelled'
WHERE i.customer_id = ?
  AND i.tenant_id = ?
  AND i.status = 'Paid'
GROUP BY i.id
HAVING available_for_credit > 0
ORDER BY i.invoice_date DESC
```

**Frontend Usage**:
- **File**: `src/components/credit-notes/create-credit-note-modal.tsx`
- **Called on**: Customer selected in credit note form
- **Purpose**: Show invoices available for credit

---

## 12.6 GET /api/v1/reports/export

**Description**: Export data as CSV or Excel.

**Authentication**: Required

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| type | string | Yes | invoices, customers, receipts, credit_notes |
| format | string | No | csv or xlsx (default: csv) |
| dateFrom | date | No | Filter from date |
| dateTo | date | No | Filter to date |

**Success Response (200 OK)**:
- Content-Type: `text/csv` or `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Content-Disposition: `attachment; filename="invoices-2024-01-15.csv"`
- Body: CSV or Excel file

**Business Logic**:
1. Get tenant_id from JWT
2. Validate type is one of allowed values
3. Query data based on type with date filters
4. Generate CSV or Excel file
5. Stream to client

**Frontend Usage**:
- Export buttons on list pages
- Purpose: Download data for analysis

---

# 13. COMMON PATTERNS

## 13.1 Authentication

All protected endpoints require JWT Bearer token:

**Request Header**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Token Payload**:
```json
{
  "sub": "user-uuid",
  "tenant_id": "tenant-uuid",
  "email": "user@example.com",
  "role": "admin",
  "exp": 1234567890
}
```

**Token Validation**:
1. Verify signature with SECRET_KEY
2. Check expiration (exp field)
3. Extract tenant_id and user_id
4. Set in request context for all queries

---

## 13.2 Tenant Isolation

**All database queries MUST filter by tenant_id**:

```sql
-- GOOD
SELECT * FROM customers WHERE tenant_id = ? AND id = ?

-- BAD (security risk!)
SELECT * FROM customers WHERE id = ?
```

**Middleware Implementation**:
1. Extract tenant_id from JWT
2. Inject into all ORM queries automatically
3. Prevent cross-tenant data access

---

## 13.3 Error Response Format

**Standard Error Structure**:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field1": "Field-specific error",
      "field2": "Another error"
    }
  }
}
```

**Common Error Codes**:
- `VALIDATION_ERROR` - Input validation failed
- `UNAUTHORIZED` - Missing or invalid token
- `FORBIDDEN` - Insufficient permissions
- `NOT_FOUND` - Resource not found
- `CONFLICT` - Duplicate resource (unique constraint)
- `PAYMENT_REQUIRED` - Subscription limit reached
- `INTERNAL_ERROR` - Server error

**HTTP Status Codes**:
- `200` OK - Success
- `201` Created - Resource created
- `400` Bad Request - Validation error
- `401` Unauthorized - Authentication required
- `403` Forbidden - Authorization failed
- `404` Not Found - Resource not found
- `409` Conflict - Duplicate or constraint violation
- `402` Payment Required - Subscription issue
- `423` Locked - Trial expired
- `500` Internal Server Error - Server error

---

## 13.4 Pagination Format

**Query Parameters**:
```
?page=1&limit=50
```

**Response Structure**:
```json
{
  "data": [...],
  "pagination": {
    "total": 250,
    "page": 1,
    "limit": 50,
    "totalPages": 5,
    "hasMore": true
  }
}
```

**Calculation**:
```javascript
totalPages = Math.ceil(total / limit);
hasMore = page < totalPages;
offset = (page - 1) * limit;
```

---

## 13.5 Date Formats

**Request/Response**:
- Dates: ISO 8601 format `YYYY-MM-DD`
- Timestamps: ISO 8601 with timezone `YYYY-MM-DDTHH:mm:ssZ`

**Examples**:
```json
{
  "invoiceDate": "2024-01-15",
  "createdAt": "2024-01-15T10:30:00Z"
}
```

---

## 13.6 Currency Format

**All monetary amounts**:
- Type: Decimal/Float
- Precision: 2 decimal places
- Currency: INR (Indian Rupee)

**Example**:
```json
{
  "total": 59000.00,
  "currency": "INR"
}
```

---

## 13.7 Audit Logging

**All create/update/delete operations should log**:

```json
{
  "user_id": "uuid",
  "tenant_id": "uuid",
  "entity_type": "invoice",
  "entity_id": "uuid",
  "action": "create",
  "old_values": null,
  "new_values": {...},
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

## 13.8 Subscription Limit Enforcement

**Before creating records, check limits**:

```javascript
// Example for invoice creation
const tenant = await getTenant(tenant_id);
if (tenant.subscription_status === 'trial' || tenant.subscription_status === 'expired') {
  if (tenant.current_invoice_count >= FREE_TIER_INVOICE_LIMIT) {
    return 402; // Payment Required
  }
}
```

**Limits to enforce**:
- Free tier: 10 invoices/month, 50 customers, 1 user
- Trial: No limits (14 days)
- Paid: No limits

---

# SUMMARY

## Total API Endpoints: 46

### By Category:
- **Authentication**: 5 endpoints
- **Dashboard**: 4 endpoints
- **Company**: 2 endpoints
- **Customers**: 5 endpoints
- **Service Types**: 4 endpoints
- **Client Types**: 4 endpoints
- **Account Managers**: 1 endpoint
- **Invoices**: 7 endpoints
- **Receipts**: 3 endpoints
- **Credit Notes**: 3 endpoints
- **GST Settings**: 2 endpoints
- **Helpers**: 6 endpoints

### By HTTP Method:
- **GET**: 26 endpoints (read operations)
- **POST**: 14 endpoints (create operations)
- **PUT**: 4 endpoints (update operations)
- **DELETE**: 2 endpoints (delete operations)

### Critical Features:
✅ Multi-tenant isolation (all queries filtered by tenant_id)
✅ Trial tracking and limit enforcement
✅ Email authentication with verification
✅ Complex calculations (invoices, taxes, aging)
✅ Payment allocation logic
✅ Status management (invoices, receipts)
✅ Number auto-generation
✅ PDF generation
✅ Email notifications
✅ Audit logging
✅ RBAC (role-based access control)
✅ GST/Indian market support
✅ Comprehensive error handling
✅ Pagination and filtering
✅ Data export functionality

---

## Implementation Priorities

### Phase 1 (Core):
1. Authentication APIs (register, login, verify)
2. Company API (profile setup)
3. Customer APIs (CRUD)
4. Service/Client Type APIs (configuration)

### Phase 2 (Billing):
1. Invoice APIs (CRUD + PDF)
2. Receipt APIs (payment tracking)
3. Number generation helpers

### Phase 3 (Advanced):
1. Dashboard APIs (metrics, charts)
2. Credit Note APIs
3. GST Settings APIs
4. Helper APIs (pending invoices, etc.)

### Phase 4 (Enhancement):
1. Email sending
2. Data export
3. Advanced filtering
4. Audit logging

---

**This specification provides everything needed to implement a complete, production-ready backend for the RMS Billing Software!**
