"""
Customer, Client Type, and Account Manager models
"""
import uuid
from sqlalchemy import Column, String, Integer, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, TenantMixin


class ClientType(Base, TimestampMixin, TenantMixin):
    """
    Client Type model - categorizes customers (e.g., VIP, Regular, Wholesale)
    """

    __tablename__ = "client_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    payment_terms = Column(Integer, default=30, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    customers = relationship("Customer", back_populates="client_type")

    def __repr__(self):
        return f"<ClientType {self.code} - {self.name}>"


class AccountManager(Base, TimestampMixin, TenantMixin):
    """
    Account Manager model - users who manage customer accounts
    """

    __tablename__ = "account_managers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    tenant = relationship("Tenant")

    def __repr__(self):
        return f"<AccountManager {self.name}>"


class Customer(Base, TimestampMixin, TenantMixin):
    """
    Customer/Client model - represents customers who receive invoices
    """

    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)

    # Client type reference
    client_type_id = Column(
        UUID(as_uuid=True), ForeignKey("client_types.id"), nullable=True
    )

    # Contact information
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    address_line3 = Column(String(255), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    whatsapp = Column(String(20), nullable=True)
    phone = Column(String(20), nullable=True)
    contact_person = Column(String(255), nullable=True)
    customer_note = Column(Text, nullable=True)

    # Tax information
    gst_number = Column(String(15), nullable=True)
    pan_number = Column(String(10), nullable=True)
    gst_exempted = Column(Boolean, default=False, nullable=False)
    gst_exemption_reason = Column(Text, nullable=True)

    # Business terms
    payment_terms = Column(Integer, default=30, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Audit fields
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="customers")
    client_type = relationship("ClientType", back_populates="customers")
    invoices = relationship("Invoice", back_populates="customer")
    receipts = relationship("Receipt", back_populates="customer")
    credit_notes = relationship("CreditNote", back_populates="customer")

    def __repr__(self):
        return f"<Customer {self.code} - {self.name}>"
