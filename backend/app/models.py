import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

JSON_VALUE = JSON().with_variant(JSONB, "postgresql")


def utcnow():
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    sector: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    users: Mapped[list["User"]] = relationship(back_populates="organization")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("organization_id", "username", name="uq_user_org_username"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(120), index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30), index=True)  # superadmin, admin, employee
    employee_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    organization: Mapped[Organization | None] = relationship(back_populates="users")


class ResourceRecord(Base):
    """Tenant-scoped business record. Payload preserves the existing index.html data shape."""
    __tablename__ = "resource_records"
    __table_args__ = (
        UniqueConstraint("organization_id", "resource_type", "external_id", name="uq_org_resource_external_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    resource_type: Mapped[str] = mapped_column(String(60), index=True)
    external_id: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSON_VALUE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    record_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
