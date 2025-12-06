"""
Company model - tenant's company profile/information
"""
import uuid
from sqlalchemy import Column, String, Date, Text, ForeignKey, Boolean, JSON
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
    pan = Column(String(10), nullable=False)  # Changed from tax_id to pan
    registration_number = Column(String(100), nullable=True)  # Keeping this for backward compatibility
    
    # Financial year
    financial_year_from = Column(Date, nullable=False)  # Changed from financial_year_start
    financial_year_to = Column(Date, nullable=False)  # New field
    
    # Address details - expanded to 3 lines
    address_line1 = Column(String(255), nullable=False)
    address_line2 = Column(String(255), nullable=True)
    address_line3 = Column(String(255), nullable=True)
    state = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)

    # Contact numbers - 3 contact fields
    contact_no1 = Column(String(20), nullable=False)
    contact_no2 = Column(String(20), nullable=True)
    contact_no3 = Column(String(20), nullable=True)
    
    # GST details
    gst_applicable = Column(Boolean, default=False, nullable=False)
    gst_number = Column(String(15), nullable=True)
    gst_state_code = Column(String(2), nullable=True)
    gst_compounding_company = Column(Boolean, default=False, nullable=False)
    
    # Group company details
    group_company = Column(Boolean, default=False, nullable=False)
    group_code = Column(String(50), nullable=True)
    
    # Bank details (stored as JSON object)
    bank_details = Column(JSON, nullable=False)
    
    # Legacy fields - keeping for backward compatibility (can be removed later)
    contact_name = Column(String(100), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    currency = Column(String(3), default="INR", nullable=True)
    industry = Column(String(100), nullable=True)
    company_size = Column(String(50), nullable=True)

    # Audit fields
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="companies")

    def __repr__(self):
        return f"<Company {self.name}>"
