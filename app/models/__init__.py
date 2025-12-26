"""
SQLAlchemy models for the application
"""
from app.models.base import Base, TimestampMixin, TenantMixin
from app.models.tenant import Tenant, Subscription
from app.models.user import User, Session, EmailVerification
from app.models.company import Company
from app.models.customer import Customer, ClientType  # AccountManager removed
from app.models.service import ServiceType
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.receipt import Receipt, ReceiptAllocation
from app.models.credit_note import CreditNote
from app.models.gst import GSTSetting, TaxRate
from app.models.audit import AuditLog

__all__ = [
    "Base",
    "TimestampMixin",
    "TenantMixin",
    "Tenant",
    "Subscription",
    "User",
    "Session",
    "EmailVerification",
    "Company",
    "Customer",
    "ClientType",
    # "AccountManager",  # Removed
    "ServiceType",
    "Invoice",
    "InvoiceLineItem",
    "Receipt",
    "ReceiptAllocation",
    "CreditNote",
    "GSTSetting",
    "TaxRate",
    "AuditLog",
]