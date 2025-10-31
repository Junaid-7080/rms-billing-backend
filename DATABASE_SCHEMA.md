# RMS Billing Software - Database Schema Documentation

## Overview

This document describes the complete database schema for the RMS (Revenue Management System) Billing Software. The application uses a **multi-tenant architecture** with **shared database + shared schema** approach, where all tenants share the same tables but data is isolated using `tenant_id` foreign keys.

## Architecture

- **Database**: PostgreSQL 14+
- **ORM**: SQLAlchemy 2.0 with async support
- **Migrations**: Alembic
- **Tenancy Model**: Shared database, shared schema with row-level isolation
- **Primary Keys**: UUID v4 (for security and distributed systems)
- **Timestamps**: All tables include `created_at` and `updated_at`

## Multi-Tenancy Strategy

### Tenant Isolation
- Every business entity table includes a `tenant_id` column (UUID, foreign key to `tenants.id`)
- All queries must filter by `tenant_id` to ensure data isolation
- Tenant context is set via middleware and automatically injected into queries
- Unique constraints are scoped to `tenant_id` where applicable

### Benefits
- Cost-effective for SaaS (single database)
- Easy maintenance and upgrades
- Simple backup and restore
- Feature updates roll out to all tenants simultaneously

### Security Considerations
- Application-level enforcement of tenant isolation
- Database row-level security (RLS) as additional layer
- Audit logging for all sensitive operations
- UUID primary keys prevent ID enumeration attacks

---

## Table Structure

### 1. Core Tenant & Subscription Tables

#### `tenants`
Organization/company that uses the system. Root entity for multi-tenancy.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique tenant identifier |
| name | VARCHAR(255) | NOT NULL | Tenant/organization name |
| slug | VARCHAR(100) | NOT NULL, UNIQUE | URL-safe unique identifier |
| email | VARCHAR(255) | NOT NULL | Primary contact email |
| domain | VARCHAR(255) | NULL | Custom domain (optional) |
| subscription_status | VARCHAR(50) | NOT NULL, DEFAULT 'trial' | trial, active, expired, cancelled, suspended |
| trial_start_date | TIMESTAMP | NULL | When trial period started |
| trial_end_date | TIMESTAMP | NULL | When trial expires (14 days from start) |
| is_trial_used | BOOLEAN | NOT NULL, DEFAULT false | Prevents multiple trials |
| converted_to_paid_at | TIMESTAMP | NULL | When user upgraded to paid |
| subscription_start_date | TIMESTAMP | NULL | Paid subscription start |
| subscription_end_date | TIMESTAMP | NULL | Paid subscription end |
| current_invoice_count | INTEGER | NOT NULL, DEFAULT 0 | Count for enforcing limits |
| current_customer_count | INTEGER | NOT NULL, DEFAULT 0 | Count for enforcing limits |
| current_user_count | INTEGER | NOT NULL, DEFAULT 0 | Count for enforcing limits |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Soft delete flag |
| settings | JSONB | NULL | Flexible tenant settings |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `slug` (UNIQUE)

**Business Rules:**
- Trial lasts 14 days from `trial_start_date`
- After trial: either limited free tier or hard lock
- `is_trial_used` prevents creating multiple trials with same email

---

#### `subscriptions`
Tracks subscription details and billing information for each tenant.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique subscription identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| plan_type | VARCHAR(50) | NOT NULL, DEFAULT 'trial' | trial, paid |
| billing_cycle | VARCHAR(20) | NULL | monthly, yearly (NULL for trial) |
| amount | DECIMAL(10,2) | NOT NULL, DEFAULT 0 | Subscription price |
| currency | VARCHAR(3) | NOT NULL, DEFAULT 'INR' | Currency code |
| is_trial | BOOLEAN | NOT NULL, DEFAULT true | Is this a trial subscription |
| trial_start_date | TIMESTAMP | NULL | Trial start date |
| trial_end_date | TIMESTAMP | NULL | Trial end date |
| trial_days_remaining | INTEGER | NULL | Days left in trial |
| status | VARCHAR(50) | NOT NULL, DEFAULT 'active' | active, expired, cancelled, suspended |
| next_billing_date | TIMESTAMP | NULL | Next payment due date |
| payment_method | VARCHAR(50) | NULL | Payment method used |
| last_payment_date | TIMESTAMP | NULL | Last successful payment |
| last_payment_amount | DECIMAL(10,2) | NULL | Last payment amount |
| notes | TEXT | NULL | Internal notes |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`

**Business Rules:**
- Each tenant typically has one active subscription
- Trial subscriptions have `is_trial=true` and `plan_type='trial'`
- Paid subscriptions require `billing_cycle`, `amount`, and `payment_method`

---

### 2. User & Authentication Tables

#### `users`
System users who access the application. Users belong to a tenant and have roles.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique user identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| email | VARCHAR(255) | NOT NULL | User email (unique per tenant) |
| password_hash | VARCHAR(255) | NOT NULL | Bcrypt hashed password |
| first_name | VARCHAR(100) | NULL | User first name |
| last_name | VARCHAR(100) | NULL | User last name |
| role | VARCHAR(50) | NOT NULL, DEFAULT 'user' | admin, manager, user |
| email_verified | BOOLEAN | NOT NULL, DEFAULT false | Email verification status |
| email_verified_at | TIMESTAMP | NULL | When email was verified |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Account active status |
| last_login_at | TIMESTAMP | NULL | Last successful login |
| deleted_at | TIMESTAMP | NULL | Soft delete timestamp |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`
- `email`
- UNIQUE constraint on (tenant_id, email)

**Business Rules:**
- Email must be unique within a tenant (not globally)
- Password stored as bcrypt hash (never plaintext)
- First user in tenant automatically gets 'admin' role
- Users with `deleted_at` set are soft-deleted

**Roles:**
- **admin**: Full access, can manage users, settings, billing
- **manager**: Can create/edit invoices, customers, reports
- **user**: Read-only or limited write access

---

#### `sessions`
Tracks active user sessions and refresh tokens for authentication.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique session identifier |
| user_id | UUID | NOT NULL, FK(users.id) | User reference |
| refresh_token | VARCHAR(500) | NOT NULL, UNIQUE | JWT refresh token |
| access_token | VARCHAR(500) | NULL | JWT access token (optional) |
| expires_at | TIMESTAMP | NOT NULL | Token expiration time |
| ip_address | VARCHAR(45) | NULL | Client IP address |
| user_agent | TEXT | NULL | Client user agent |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Session status |
| revoked_at | TIMESTAMP | NULL | When session was revoked |
| created_at | TIMESTAMP | NOT NULL | Session creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `user_id`
- `refresh_token` (UNIQUE)

**Business Rules:**
- One refresh token per session
- Sessions expire after 7 days (configurable)
- Revoked sessions cannot be reused
- IP and user agent logged for security

---

#### `email_verifications`
Stores email verification tokens for new user registration.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique verification identifier |
| user_id | UUID | NOT NULL, FK(users.id) | User reference |
| token | VARCHAR(255) | NOT NULL, UNIQUE | Verification token |
| expires_at | TIMESTAMP | NOT NULL | Token expiration (24 hours) |
| is_used | BOOLEAN | NOT NULL, DEFAULT false | Has token been used |
| used_at | TIMESTAMP | NULL | When token was used |
| created_at | TIMESTAMP | NOT NULL | Token creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `user_id`
- `token` (UNIQUE)

**Business Rules:**
- Token expires after 24 hours
- One-time use only
- New verification emails invalidate old tokens

---

### 3. Company Profile Table

#### `companies`
Company profile/information for each tenant. Typically one per tenant.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique company identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| name | VARCHAR(255) | NOT NULL | Company legal name |
| address | TEXT | NULL | Company address |
| registration_number | VARCHAR(100) | NULL | Company registration number |
| tax_id | VARCHAR(100) | NULL | Tax identification number |
| gst_number | VARCHAR(15) | NULL | GST number (India) |
| contact_name | VARCHAR(100) | NULL | Primary contact person |
| contact_email | VARCHAR(255) | NULL | Contact email |
| contact_phone | VARCHAR(20) | NULL | Contact phone |
| financial_year_start | DATE | NULL | Financial year start date |
| currency | VARCHAR(3) | NOT NULL, DEFAULT 'INR' | Default currency |
| industry | VARCHAR(100) | NULL | Industry/sector |
| company_size | VARCHAR(50) | NULL | Company size category |
| created_by | UUID | FK(users.id) | User who created |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`

**Business Rules:**
- Most tenants have exactly one company profile
- Created during tenant onboarding
- GST number required for Indian businesses

---

### 4. Customer Management Tables

#### `client_types`
Categories/types of customers (e.g., VIP, Regular, Wholesale).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique client type identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| code | VARCHAR(50) | NOT NULL | Short code (e.g., "VIP") |
| name | VARCHAR(255) | NOT NULL | Display name |
| description | TEXT | NULL | Description |
| payment_terms | INTEGER | NOT NULL, DEFAULT 30 | Default payment terms (days) |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Active status |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`
- UNIQUE constraint on (tenant_id, code)

**Business Rules:**
- Code must be unique within tenant
- Payment terms in days (e.g., 30, 60, 90)
- Inactive types hidden in dropdowns

---

#### `account_managers`
Users who manage customer accounts and relationships.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique manager identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| user_id | UUID | FK(users.id) | Linked user account (optional) |
| name | VARCHAR(255) | NOT NULL | Manager name |
| email | VARCHAR(255) | NOT NULL | Manager email |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Active status |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`

**Business Rules:**
- Can be linked to a user account or standalone
- Used for customer assignment and reporting

---

#### `customers`
Customers/clients who receive invoices and make payments.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique customer identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| code | VARCHAR(50) | NOT NULL | Customer code |
| name | VARCHAR(255) | NOT NULL | Customer name |
| client_type_id | UUID | FK(client_types.id) | Client type reference |
| address | TEXT | NULL | Customer address |
| email | VARCHAR(255) | NULL | Customer email |
| whatsapp | VARCHAR(20) | NULL | WhatsApp number |
| phone | VARCHAR(20) | NULL | Phone number |
| contact_person | VARCHAR(255) | NULL | Primary contact name |
| gst_number | VARCHAR(15) | NULL | GST number |
| pan_number | VARCHAR(10) | NULL | PAN number (India) |
| payment_terms | INTEGER | NOT NULL, DEFAULT 30 | Payment terms (days) |
| account_manager_id | UUID | FK(account_managers.id) | Assigned manager |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Active status |
| created_by | UUID | FK(users.id) | User who created |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`
- UNIQUE constraint on (tenant_id, code)

**Business Rules:**
- Customer code must be unique within tenant
- GST and PAN required for Indian B2B customers
- Inactive customers hidden but data preserved

---

### 5. Service Configuration Table

#### `service_types`
Types of services that can be invoiced.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique service type identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| code | VARCHAR(50) | NOT NULL | Service code |
| name | VARCHAR(255) | NOT NULL | Service name |
| description | TEXT | NULL | Description |
| tax_rate | DECIMAL(5,2) | NOT NULL, DEFAULT 0 | Default tax rate (%) |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Active status |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`
- UNIQUE constraint on (tenant_id, code)

**Business Rules:**
- Code unique within tenant
- Tax rate can be overridden per invoice line item
- Inactive services hidden in dropdowns

---

### 6. Invoice & Billing Tables

#### `invoices`
Invoices sent to customers for services/products.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique invoice identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| invoice_number | VARCHAR(50) | NOT NULL | Invoice number |
| invoice_date | DATE | NOT NULL | Invoice date |
| due_date | DATE | NOT NULL | Payment due date |
| customer_id | UUID | NOT NULL, FK(customers.id) | Customer reference |
| customer_gst | VARCHAR(15) | NULL | Customer GST (if different) |
| reference_number | VARCHAR(100) | NULL | External reference |
| subtotal | DECIMAL(15,2) | NOT NULL, DEFAULT 0 | Amount before tax |
| tax_total | DECIMAL(15,2) | NOT NULL, DEFAULT 0 | Total tax amount |
| total | DECIMAL(15,2) | NOT NULL, DEFAULT 0 | Grand total |
| status | VARCHAR(50) | NOT NULL, DEFAULT 'draft' | draft, pending, paid, overdue, cancelled, partially_paid |
| notes | TEXT | NULL | Invoice notes/terms |
| created_by | UUID | FK(users.id) | User who created |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`
- `customer_id`
- UNIQUE constraint on (tenant_id, invoice_number)

**Business Rules:**
- Invoice number auto-generated and unique per tenant
- Status automatically updated based on payments
- Overdue status set when due_date passed and not paid
- Amounts calculated from line items

**Status Transitions:**
- draft → pending (when finalized)
- pending → paid (when fully paid)
- pending → partially_paid (when partially paid)
- pending → overdue (when due_date passed)
- any → cancelled (manual cancellation)

---

#### `invoice_line_items`
Individual line items within an invoice.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique line item identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| invoice_id | UUID | NOT NULL, FK(invoices.id) CASCADE | Invoice reference |
| service_type_id | UUID | FK(service_types.id) | Service type reference |
| description | TEXT | NULL | Line item description |
| quantity | DECIMAL(10,2) | NOT NULL, DEFAULT 1 | Quantity |
| rate | DECIMAL(15,2) | NOT NULL, DEFAULT 0 | Unit price |
| amount | DECIMAL(15,2) | NOT NULL, DEFAULT 0 | quantity × rate |
| tax_rate | DECIMAL(5,2) | NOT NULL, DEFAULT 0 | Tax rate (%) |
| tax_amount | DECIMAL(15,2) | NOT NULL, DEFAULT 0 | Calculated tax |
| total | DECIMAL(15,2) | NOT NULL, DEFAULT 0 | amount + tax_amount |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`
- `invoice_id`

**Business Rules:**
- Deleted when parent invoice deleted (CASCADE)
- amount = quantity × rate
- tax_amount = amount × (tax_rate / 100)
- total = amount + tax_amount

---

### 7. Payment & Receipt Tables

#### `receipts`
Payments received from customers.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique receipt identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| receipt_number | VARCHAR(50) | NOT NULL | Receipt number |
| receipt_date | DATE | NOT NULL | Payment received date |
| customer_id | UUID | NOT NULL, FK(customers.id) | Customer reference |
| payment_method | VARCHAR(50) | NULL | bank_transfer, cheque, cash, upi, card |
| amount | DECIMAL(15,2) | NOT NULL, DEFAULT 0 | Payment amount |
| status | VARCHAR(50) | NOT NULL, DEFAULT 'pending' | pending, cleared, bounced, cancelled |
| notes | TEXT | NULL | Payment notes |
| created_by | UUID | FK(users.id) | User who created |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`
- `customer_id`
- UNIQUE constraint on (tenant_id, receipt_number)

**Business Rules:**
- Receipt number auto-generated per tenant
- Can be allocated to multiple invoices
- Status 'pending' until payment clears

---

#### `receipt_allocations`
Links receipts to invoices, tracking payment allocation.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique allocation identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| receipt_id | UUID | NOT NULL, FK(receipts.id) CASCADE | Receipt reference |
| invoice_id | UUID | NOT NULL, FK(invoices.id) CASCADE | Invoice reference |
| allocated_amount | DECIMAL(15,2) | NOT NULL, DEFAULT 0 | Amount allocated |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`
- `receipt_id`
- `invoice_id`

**Business Rules:**
- One receipt can be allocated to multiple invoices
- Sum of allocations cannot exceed receipt amount
- Invoice status updated when fully allocated

---

### 8. Credit Notes Table

#### `credit_notes`
Credit notes issued to customers (refunds, adjustments).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique credit note identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| credit_note_number | VARCHAR(50) | NOT NULL | Credit note number |
| credit_note_date | DATE | NOT NULL | Issue date |
| customer_id | UUID | NOT NULL, FK(customers.id) | Customer reference |
| invoice_id | UUID | FK(invoices.id) | Related invoice (optional) |
| reason | VARCHAR(255) | NULL | Reason for credit |
| amount | DECIMAL(15,2) | NOT NULL, DEFAULT 0 | Credit amount |
| gst_amount | DECIMAL(15,2) | NOT NULL, DEFAULT 0 | GST amount |
| total_credit | DECIMAL(15,2) | NOT NULL, DEFAULT 0 | Total credit |
| status | VARCHAR(50) | NOT NULL, DEFAULT 'draft' | draft, issued, applied, cancelled |
| notes | TEXT | NULL | Additional notes |
| created_by | UUID | FK(users.id) | User who created |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`
- `customer_id`
- `invoice_id`
- UNIQUE constraint on (tenant_id, credit_note_number)

**Business Rules:**
- Auto-generated credit note number per tenant
- Can be linked to invoice or standalone
- Reduces customer outstanding balance

---

### 9. GST & Tax Configuration Tables

#### `gst_settings`
GST/tax configuration for each tenant.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique setting identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| is_gst_applicable | BOOLEAN | NOT NULL, DEFAULT false | GST enabled |
| gst_number | VARCHAR(15) | NULL | Company GST number |
| effective_date | DATE | NULL | GST effective from |
| default_rate | DECIMAL(5,2) | NOT NULL, DEFAULT 0 | Default tax rate (%) |
| display_format | VARCHAR(50) | NULL | inclusive, exclusive |
| filing_frequency | VARCHAR(20) | NULL | monthly, quarterly, annually |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id` (UNIQUE - one per tenant)

**Business Rules:**
- One GST setting per tenant
- Required for Indian businesses
- Filing frequency affects reporting

---

#### `tax_rates`
Different tax rates for different categories/services.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique tax rate identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| gst_setting_id | UUID | FK(gst_settings.id) | GST setting reference |
| category | VARCHAR(100) | NOT NULL | Tax category name |
| rate | DECIMAL(5,2) | NOT NULL, DEFAULT 0 | Tax rate (%) |
| effective_from | DATE | NOT NULL | Effective start date |
| description | TEXT | NULL | Description |
| created_at | TIMESTAMP | NOT NULL | Record creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`

**Business Rules:**
- Multiple tax rates per tenant
- Used for different product/service categories
- Historical rates preserved

---

### 10. Audit & Compliance Table

#### `audit_logs`
Comprehensive audit trail of all system changes.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique log identifier |
| tenant_id | UUID | NOT NULL, FK(tenants.id) | Tenant reference |
| user_id | UUID | NULL | User who performed action |
| entity_type | VARCHAR(100) | NOT NULL | Entity type (invoice, customer, etc.) |
| entity_id | UUID | NULL | Entity ID |
| action | VARCHAR(50) | NOT NULL | create, update, delete |
| old_values | JSONB | NULL | Previous values (for updates) |
| new_values | JSONB | NULL | New values |
| ip_address | VARCHAR(45) | NULL | Client IP address |
| user_agent | TEXT | NULL | Client user agent |
| created_at | TIMESTAMP | NOT NULL | When action occurred |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Indexes:**
- `tenant_id`
- `user_id`
- `entity_type`
- Composite index on (entity_type, entity_id)

**Business Rules:**
- Immutable once created
- Captures all important business operations
- Used for compliance and troubleshooting
- JSONB columns for flexible data storage

---

## Entity Relationship Diagram (ERD)

```
┌─────────────┐
│   tenants   │◄─────────┐
└──────┬──────┘          │
       │                  │
       │ 1:N              │ tenant_id (all tables)
       │                  │
       ├──────────────────┼─────────────┐
       │                  │             │
       ▼                  │             ▼
┌──────────────┐    ┌─────┴──────┐  ┌──────────────┐
│subscriptions │    │   users    │  │  companies   │
└──────────────┘    └──────┬─────┘  └──────────────┘
                           │
                           │ 1:N
                           │
                    ┌──────┴──────┬──────────────┐
                    │             │              │
                    ▼             ▼              ▼
              ┌──────────┐  ┌──────────┐  ┌──────────┐
              │ sessions │  │  email   │  │  audit   │
              │          │  │verifica- │  │   logs   │
              │          │  │  tions   │  │          │
              └──────────┘  └──────────┘  └──────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│client_types  │     │account_      │     │service_types │
└──────┬───────┘     │managers      │     └──────┬───────┘
       │ 1:N         └──────┬───────┘            │ 1:N
       │                    │ 1:N                 │
       │             ┌──────┴──────┐              │
       └────────────►│  customers  │◄─────────────┘
                     └──────┬──────┘
                            │ 1:N
                            │
                     ┌──────┴──────────────────┐
                     │                         │
                     ▼                         ▼
              ┌────────────┐           ┌─────────────┐
              │  invoices  │           │  receipts   │
              └──────┬─────┘           └──────┬──────┘
                     │ 1:N                    │ 1:N
                     │                        │
                     ▼                        ▼
           ┌──────────────────┐    ┌──────────────────┐
           │ invoice_line_    │    │  receipt_        │
           │     items        │    │  allocations     │
           └──────────────────┘    └──────────────────┘

              ┌────────────┐
              │credit_notes│
              └────────────┘

┌──────────────┐
│gst_settings  │
└──────┬───────┘
       │ 1:N
       │
       ▼
┌──────────────┐
│  tax_rates   │
└──────────────┘
```

---

## Indexes Summary

For optimal query performance, the following indexes are created:

### Primary Indexes (Automatic)
- All `id` columns (PRIMARY KEY)

### Foreign Key Indexes
- All `tenant_id` columns
- `subscriptions.tenant_id`
- `users.tenant_id`
- `sessions.user_id`
- `customers.tenant_id`
- `customers.client_type_id`
- `customers.account_manager_id`
- `invoices.tenant_id`
- `invoices.customer_id`
- `invoice_line_items.invoice_id`
- `receipts.tenant_id`
- `receipts.customer_id`
- `receipt_allocations.receipt_id`
- `receipt_allocations.invoice_id`
- `credit_notes.tenant_id`
- `credit_notes.customer_id`
- `audit_logs.tenant_id`
- `audit_logs.user_id`
- `audit_logs.(entity_type, entity_id)` composite

### Unique Indexes
- `tenants.slug`
- `users.(tenant_id, email)` composite
- `sessions.refresh_token`
- `email_verifications.token`
- `customers.(tenant_id, code)` composite
- `client_types.(tenant_id, code)` composite
- `service_types.(tenant_id, code)` composite
- `invoices.(tenant_id, invoice_number)` composite
- `receipts.(tenant_id, receipt_number)` composite
- `credit_notes.(tenant_id, credit_note_number)` composite

---

## Data Types Explained

### UUID
- All primary keys use UUID v4
- 128-bit identifier, globally unique
- Prevents ID enumeration attacks
- Better for distributed systems

### VARCHAR vs TEXT
- `VARCHAR(n)`: Fixed max length, indexed efficiently
- `TEXT`: Unlimited length, used for descriptions/notes

### DECIMAL(15,2)
- Used for all monetary amounts
- 15 digits total, 2 after decimal
- Precise financial calculations (no rounding errors)

### TIMESTAMP
- UTC timezone for all timestamps
- Automatically converted by ORM

### JSONB
- Binary JSON format in PostgreSQL
- Efficient querying and indexing
- Used for flexible/schemaless data

---

## Migration Strategy

### Initial Setup
1. Run `alembic init alembic` to initialize migrations
2. Configure `alembic.ini` with database URL
3. Generate initial migration: `alembic revision --autogenerate -m "Initial schema"`
4. Apply migration: `alembic upgrade head`

### Future Changes
1. Modify SQLAlchemy models in `app/models/`
2. Generate migration: `alembic revision --autogenerate -m "Description"`
3. Review generated migration in `alembic/versions/`
4. Apply: `alembic upgrade head`
5. Rollback if needed: `alembic downgrade -1`

---

## Security Best Practices

### 1. Tenant Isolation
- Always filter by `tenant_id` in queries
- Use middleware to inject tenant context
- Validate tenant ownership before operations

### 2. Authentication
- Store passwords as bcrypt hashes (never plaintext)
- Use JWT tokens with expiration
- Implement refresh token rotation
- Log failed login attempts

### 3. Authorization
- Implement role-based access control (RBAC)
- Check user permissions before sensitive operations
- Admin role required for tenant settings

### 4. Audit Trail
- Log all create/update/delete operations
- Store old and new values for updates
- Include user, IP, and timestamp

### 5. Data Protection
- Encrypt sensitive data at rest
- Use HTTPS for all API communication
- Implement rate limiting
- Regular database backups

---

## Performance Optimization

### 1. Database Tuning
- Connection pooling (20 connections)
- Prepared statements (via SQLAlchemy)
- Query result caching where appropriate

### 2. Indexing Strategy
- Index all foreign keys
- Composite indexes for common query patterns
- Partial indexes for filtered queries

### 3. Query Optimization
- Use `select_related` / `joinedload` to avoid N+1
- Paginate large result sets
- Use aggregation queries for dashboards

### 4. Caching
- Redis for session storage
- Cache computed dashboard metrics
- Invalidate cache on data changes

---

## Backup & Recovery

### Backup Strategy
- Daily full PostgreSQL backups
- Continuous WAL archiving for point-in-time recovery
- Backup retention: 30 days
- Test restore procedures monthly

### Disaster Recovery
- Multi-region replication (for production)
- Automated failover
- RTO: 1 hour
- RPO: 5 minutes

---

## Compliance & GDPR

### Data Privacy
- Users can request data export (API endpoint)
- Right to deletion (soft delete + hard delete after 90 days)
- Data anonymization for deleted users

### Data Retention
- Active tenant data: Indefinite
- Inactive tenant data: 1 year
- Audit logs: 7 years
- Deleted user data: 90 days in soft-delete state

---

## Conclusion

This database schema provides a solid foundation for a multi-tenant SaaS billing application with:

✅ **Complete tenant isolation**
✅ **Freemium model with 14-day trial**
✅ **Email authentication (no MFA)**
✅ **Comprehensive audit logging**
✅ **Indian market support (GST, PAN)**
✅ **Scalable architecture**
✅ **Security best practices**

The schema supports the entire billing workflow from customer onboarding to invoicing, payment tracking, and financial reporting.
