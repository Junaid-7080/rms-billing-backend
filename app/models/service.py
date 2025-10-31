"""
Service Type model
"""
import uuid
from sqlalchemy import Column, String, Boolean, DECIMAL, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, TenantMixin


class ServiceType(Base, TimestampMixin, TenantMixin):
    """
    Service Type model - defines types of services that can be invoiced
    """

    __tablename__ = "service_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tax_rate = Column(DECIMAL(5, 2), default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    invoice_line_items = relationship("InvoiceLineItem", back_populates="service_type")

    def __repr__(self):
        return f"<ServiceType {self.code} - {self.name}>"
