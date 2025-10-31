"""
Audit Log model
"""
import uuid
from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, TenantMixin


class AuditLog(Base, TimestampMixin, TenantMixin):
    """
    Audit Log model - tracks all important changes in the system
    """

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # User who performed the action
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Entity information
    entity_type = Column(
        String(100), nullable=False, index=True
    )  # 'invoice', 'customer', etc.
    entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Action performed
    action = Column(String(50), nullable=False)  # 'create', 'update', 'delete'

    # Change tracking
    old_values = Column(JSONB, nullable=True)
    new_values = Column(JSONB, nullable=True)

    # Request metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Relationships
    tenant = relationship("Tenant")

    def __repr__(self):
        return f"<AuditLog {self.entity_type} {self.action} by {self.user_id}>"
