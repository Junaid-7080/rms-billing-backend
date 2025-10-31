"""
Invoice and Invoice Line Item models
"""
import uuid
from sqlalchemy import Column, String, Date, DECIMAL, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, TenantMixin


class Invoice(Base, TimestampMixin, TenantMixin):
    """
    Invoice model - represents invoices sent to customers
    """

    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number = Column(String(50), nullable=False)
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)

    # Customer reference
    customer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_gst = Column(String(15), nullable=True)
    reference_number = Column(String(100), nullable=True)

    # Amounts
    subtotal = Column(DECIMAL(15, 2), default=0, nullable=False)
    tax_total = Column(DECIMAL(15, 2), default=0, nullable=False)
    total = Column(DECIMAL(15, 2), default=0, nullable=False)

    # Status (draft, pending, paid, overdue, cancelled, partially_paid)
    status = Column(String(50), default="draft", nullable=False)

    # Notes
    notes = Column(Text, nullable=True)

    # Audit fields
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="invoices")
    customer = relationship("Customer", back_populates="invoices")
    line_items = relationship(
        "InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan"
    )
    receipt_allocations = relationship("ReceiptAllocation", back_populates="invoice")
    credit_notes = relationship("CreditNote", back_populates="invoice")

    def __repr__(self):
        return f"<Invoice {self.invoice_number} - {self.total}>"


class InvoiceLineItem(Base, TimestampMixin, TenantMixin):
    """
    Invoice Line Item model - individual line items within an invoice
    """

    __tablename__ = "invoice_line_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Service type reference
    service_type_id = Column(
        UUID(as_uuid=True), ForeignKey("service_types.id"), nullable=True
    )

    # Line item details
    description = Column(Text, nullable=True)
    quantity = Column(DECIMAL(10, 2), default=1, nullable=False)
    rate = Column(DECIMAL(15, 2), default=0, nullable=False)
    amount = Column(DECIMAL(15, 2), default=0, nullable=False)

    # Tax calculation
    tax_rate = Column(DECIMAL(5, 2), default=0, nullable=False)
    tax_amount = Column(DECIMAL(15, 2), default=0, nullable=False)
    total = Column(DECIMAL(15, 2), default=0, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    invoice = relationship("Invoice", back_populates="line_items")
    service_type = relationship("ServiceType", back_populates="invoice_line_items")

    def __repr__(self):
        return f"<InvoiceLineItem {self.invoice_id} - {self.total}>"
