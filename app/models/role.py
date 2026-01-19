"""Role model for tenant-specific authorization roles"""
import uuid
from sqlalchemy import Column, String, Boolean, Text, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Role(Base, TimestampMixin):
    """Stores named roles that can be managed per tenant"""

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    permissions = Column(JSONB, nullable=True)
    is_system = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    tenant = relationship("Tenant")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<Role {self.name} (tenant={self.tenant_id})>"
