"""
Tenant and Subscription models
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime, DECIMAL, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Tenant(Base, TimestampMixin):
    """
    Tenant/Organization model for multi-tenancy
    Each tenant represents a separate company/organization using the system
    """

    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    domain = Column(String(255), nullable=True)

    # Trial & Subscription Status
    subscription_status = Column(
        String(50), default="trial", nullable=False
    )  # trial, active, expired, cancelled, suspended
    trial_start_date = Column(DateTime, nullable=True)
    trial_end_date = Column(DateTime, nullable=True)
    is_trial_used = Column(Boolean, default=False, nullable=False)
    converted_to_paid_at = Column(DateTime, nullable=True)
    subscription_start_date = Column(DateTime, nullable=True)
    subscription_end_date = Column(DateTime, nullable=True)

    # Usage Tracking (for enforcing limits)
    current_invoice_count = Column(Integer, default=0, nullable=False)
    current_customer_count = Column(Integer, default=0, nullable=False)
    current_user_count = Column(Integer, default=0, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Settings (flexible JSON storage)
    settings = Column(JSONB, nullable=True)

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    subscriptions = relationship(
        "Subscription", back_populates="tenant", cascade="all, delete-orphan"
    )
    companies = relationship(
        "Company", back_populates="tenant", cascade="all, delete-orphan"
    )
    customers = relationship(
        "Customer", back_populates="tenant", cascade="all, delete-orphan"
    )
    invoices = relationship(
        "Invoice", back_populates="tenant", cascade="all, delete-orphan"
    )
    receipts = relationship(
        "Receipt", back_populates="tenant", cascade="all, delete-orphan"
    )
    credit_notes = relationship(
        "CreditNote", back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Tenant {self.name} ({self.slug})>"


class Subscription(Base, TimestampMixin):
    """
    Subscription model to track tenant's subscription details
    Handles trial, paid subscriptions, and billing
    """

    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Subscription Details
    plan_type = Column(String(50), default="trial", nullable=False)  # trial, paid
    billing_cycle = Column(String(20), nullable=True)  # monthly, yearly
    amount = Column(DECIMAL(10, 2), default=0, nullable=False)
    currency = Column(String(3), default="INR", nullable=False)

    # Trial Tracking
    is_trial = Column(Boolean, default=True, nullable=False)
    trial_start_date = Column(DateTime, nullable=True)
    trial_end_date = Column(DateTime, nullable=True)
    trial_days_remaining = Column(Integer, nullable=True)

    # Status
    status = Column(
        String(50), default="active", nullable=False
    )  # active, expired, cancelled, suspended

    # Payment
    next_billing_date = Column(DateTime, nullable=True)
    payment_method = Column(String(50), nullable=True)
    last_payment_date = Column(DateTime, nullable=True)
    last_payment_amount = Column(DECIMAL(10, 2), nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription {self.tenant_id} - {self.plan_type} ({self.status})>"
