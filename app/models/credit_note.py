"""
Credit Note model
"""
import uuid
from sqlalchemy import Column, String, Date, DECIMAL, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, TenantMixin


class CreditNote(Base, TimestampMixin, TenantMixin):
    """
    Credit Note model - represents credit notes issued to customers
    """

    __tablename__ = "credit_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    credit_note_number = Column(String(50), nullable=False)
    credit_note_date = Column(Date, nullable=False)

    # Customer reference
    customer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Invoice reference (optional - credit note might not be against a specific invoice)
    invoice_id = Column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True, index=True
    )

    # Credit note details
    reason = Column(String(255), nullable=True)
    amount = Column(DECIMAL(15, 2), default=0, nullable=False)
    gst_amount = Column(DECIMAL(15, 2), default=0, nullable=False)
    total_credit = Column(DECIMAL(15, 2), default=0, nullable=False)

    # Status (draft, issued, applied, cancelled)
    status = Column(String(50), default="draft", nullable=False)

    # Notes
    notes = Column(Text, nullable=True)

    # Audit fields
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="credit_notes")
    customer = relationship("Customer", back_populates="credit_notes")
    invoice = relationship("Invoice", back_populates="credit_notes")

    def __repr__(self):
        return f"<CreditNote {self.credit_note_number} - {self.total_credit}>"
