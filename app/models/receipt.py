"""
Receipt and Receipt Allocation models
"""
import uuid
from sqlalchemy import Column, String, Date, DECIMAL, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, TenantMixin


class Receipt(Base, TimestampMixin, TenantMixin):
    """
    Receipt model - represents payments received from customers
    """

    __tablename__ = "receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    receipt_number = Column(String(50), nullable=False)
    receipt_date = Column(Date, nullable=False)

    # Customer reference
    customer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Payment details
    payment_method = Column(
        String(50), nullable=True
    )  # bank_transfer, cheque, cash, upi, card
    amount = Column(DECIMAL(15, 2), default=0, nullable=False)

    # Status (pending, cleared, bounced, cancelled)
    status = Column(String(50), default="pending", nullable=False)

    # Notes
    notes = Column(Text, nullable=True)

    # Audit fields
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="receipts")
    customer = relationship("Customer", back_populates="receipts")
    allocations = relationship(
        "ReceiptAllocation", back_populates="receipt", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Receipt {self.receipt_number} - {self.amount}>"


class ReceiptAllocation(Base, TimestampMixin, TenantMixin):
    """
    Receipt Allocation model - links receipts to invoices
    Tracks how receipt amounts are allocated against invoices
    """

    __tablename__ = "receipt_allocations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    receipt_id = Column(
        UUID(as_uuid=True),
        ForeignKey("receipts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id = Column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Allocation amount
    allocated_amount = Column(DECIMAL(15, 2), default=0, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    receipt = relationship("Receipt", back_populates="allocations")
    invoice = relationship("Invoice", back_populates="receipt_allocations")

    def __repr__(self):
        return f"<ReceiptAllocation {self.receipt_id} -> {self.invoice_id}>"
