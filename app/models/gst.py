"""
GST Settings and Tax Rate models
"""
import uuid
from sqlalchemy import Column, String, Boolean, Date, DECIMAL, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, TenantMixin


class GSTSetting(Base, TimestampMixin, TenantMixin):
    """
    GST Settings model - stores GST/tax configuration for each tenant
    """

    __tablename__ = "gst_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # GST configuration
    is_gst_applicable = Column(Boolean, default=False, nullable=False)
    gst_number = Column(String(15), nullable=True)
    effective_date = Column(Date, nullable=True)
    default_rate = Column(DECIMAL(5, 2), default=0, nullable=False)

    # Display and filing
    display_format = Column(String(50), nullable=True)  # inclusive, exclusive
    filing_frequency = Column(
        String(20), nullable=True
    )  # monthly, quarterly, annually

    # Relationships
    tenant = relationship("Tenant")
    tax_rates = relationship(
        "TaxRate", back_populates="gst_setting", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<GSTSetting {self.tenant_id} - {self.gst_number}>"


class TaxRate(Base, TimestampMixin, TenantMixin):
    """
    Tax Rate model - stores different tax rates for different categories
    """

    __tablename__ = "tax_rates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gst_setting_id = Column(
        UUID(as_uuid=True), ForeignKey("gst_settings.id"), nullable=True
    )

    # Tax rate details
    category = Column(String(100), nullable=False)
    rate = Column(DECIMAL(5, 2), default=0, nullable=False)
    effective_from = Column(Date, nullable=False)
    description = Column(Text, nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    gst_setting = relationship("GSTSetting", back_populates="tax_rates")

    def __repr__(self):
        return f"<TaxRate {self.category} - {self.rate}%>"
