"""
User, Session, and Email Verification models
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, TenantMixin


class User(Base, TimestampMixin, TenantMixin):
    """
    User model for authentication and authorization
    Users belong to a tenant and have roles within that tenant
    """

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)

    # Role within tenant (admin, manager, user)
    role = Column(String(50), nullable=False, default="user")

    # Email verification
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    # Soft delete
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    email_verifications = relationship(
        "EmailVerification", back_populates="user", cascade="all, delete-orphan"
    )

    # Unique constraint on tenant_id + email
    __table_args__ = (
        {"postgresql_ignore_search_path": True},
    )

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"

    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.email


class Session(Base, TimestampMixin):
    """
    Session model for tracking user sessions and refresh tokens
    """

    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Session details
    refresh_token = Column(String(500), nullable=False, unique=True, index=True)
    access_token = Column(String(500), nullable=True)
    expires_at = Column(DateTime, nullable=False)

    # Device/client information
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")

    def __repr__(self):
        return f"<Session {self.user_id} - {self.is_active}>"


class EmailVerification(Base, TimestampMixin):
    """
    Email verification tokens for user email confirmation
    """

    __tablename__ = "email_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Token details
    token = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)

    # Status
    is_used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="email_verifications")

    def __repr__(self):
        return f"<EmailVerification {self.user_id} - used:{self.is_used}>"


