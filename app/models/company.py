"""
Company model - tenant's company profile/information
"""
import uuid
from sqlalchemy import Column, String, Date, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, TenantMixin


class Company(Base, TimestampMixin, TenantMixin):
    """
    Company model - stores company profile information for each tenant
    Each tenant typically has one company profile
    """

    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Company details
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    registration_number = Column(String(100), nullable=True)
    tax_id = Column(String(100), nullable=True)
    gst_number = Column(String(15), nullable=True)

    # Contact information
    contact_name = Column(String(100), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)

    # Business details
    financial_year_start = Column(Date, nullable=True)
    currency = Column(String(3), default="INR", nullable=False)
    industry = Column(String(100), nullable=True)
    company_size = Column(String(50), nullable=True)

    # Audit fields
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="companies")

    def __repr__(self):
        return f"<Company {self.name}>"
