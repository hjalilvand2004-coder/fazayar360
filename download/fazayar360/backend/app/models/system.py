import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, PkMixin, TsMixin


class User(PkMixin, TsMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(40))
    faculty: Mapped[Optional[str]] = mapped_column(String(200))       # گروه/دانشکده متعلق
    scope_campus_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    scope_building_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(100))   # شناسه در سرویس هویت زیست‌بوم


class AuditLog(PkMixin, Base):
    """تاریخچه تغییرات حساس."""
    __tablename__ = "audit_logs"

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    actor_name: Mapped[Optional[str]] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(50))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[Optional[str]] = mapped_column(String(64))
    before: Mapped[Optional[str]] = mapped_column(Text)   # JSON
    after: Mapped[Optional[str]] = mapped_column(Text)    # JSON
    ip: Mapped[Optional[str]] = mapped_column(String(64))
    request_id: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_audit_entity", entity_type, entity_id), Index("ix_audit_created", created_at))


class ExternalReference(PkMixin, TsMixin, Base):
    """نگاشت شناسه‌های زیست‌بوم — داده مرجع با API/رویداد نسخه‌دار دریافت می‌شود، نه اتصال مستقیم به جداول پایه‌یار."""
    __tablename__ = "external_references"

    entity_type: Mapped[str] = mapped_column(String(50))   # course|course_offer|department|building|user
    external_id: Mapped[str] = mapped_column(String(100))
    source_system: Mapped[str] = mapped_column(String(50), default="payehtar360")
    source_version: Mapped[Optional[str]] = mapped_column(String(50))
    local_id: Mapped[Optional[str]] = mapped_column(String(64))
    title: Mapped[Optional[str]] = mapped_column(String(300))
    payload: Mapped[Optional[str]] = mapped_column(Text)   # JSON رکورد مرجع
    sync_status: Mapped[str] = mapped_column(String(20), default="fresh")
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("uq_ext_ref", entity_type, source_system, external_id, unique=True),
        Index("ix_ext_ref_type", entity_type, sync_status),
    )


class IntegrationEvent(PkMixin, Base):
    """ثبت دریافت و پردازش رویداد ورودی (پردازش تکرارپذیر)."""
    __tablename__ = "integration_events"

    event_type: Mapped[str] = mapped_column(String(60))
    source_system: Mapped[str] = mapped_column(String(50))
    external_event_id: Mapped[Optional[str]] = mapped_column(String(100))
    payload: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="received")  # received|processed|error
    error: Mapped[Optional[str]] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("uq_int_event", source_system, external_event_id, unique=True),)


class OutboxEvent(PkMixin, Base):
    """رویدادهای خروجی قابل‌اعتماد (الگوی Outbox) برای اطلاع زیرسیستم‌های دیگر."""
    __tablename__ = "outbox_events"

    topic: Mapped[str] = mapped_column(String(60))       # booking.confirmed | space.blocked | ...
    payload: Mapped[Optional[str]] = mapped_column(Text)  # JSON
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|published
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_outbox_status", status),)


class OptimizationRun(PkMixin, TsMixin, Base):
    """اجرای سناریوی بهینه‌سازی."""
    __tablename__ = "optimization_runs"

    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="queued")   # queued|running|completed|failed
    solver: Mapped[str] = mapped_column(String(30), default="rule_ranker")
    solution_status: Mapped[Optional[str]] = mapped_column(String(20))  # optimal|feasible|partial|no_solution
    scenario: Mapped[Optional[str]] = mapped_column(Text)               # JSON تصویر ثابت داده
    metrics: Mapped[Optional[str]] = mapped_column(Text)                # JSON مقایسه قبل/بعد
    constraints_summary: Mapped[Optional[str]] = mapped_column(Text)    # JSON محدودیت‌های مانع تخصیص
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error: Mapped[Optional[str]] = mapped_column(Text)


class OptimizationAssignment(PkMixin, Base):
    """پیشنهاد تخصیص هر جلسه در یک اجرا."""
    __tablename__ = "optimization_assignments"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("optimization_runs.id"))
    session_ref: Mapped[str] = mapped_column(String(100))
    title: Mapped[Optional[str]] = mapped_column(String(300))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_space_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    proposed_space_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    status: Mapped[str] = mapped_column(String(20), default="proposed")  # proposed|approved|applied|failed|rejected
    score_breakdown: Mapped[Optional[str]] = mapped_column(Text)  # JSON دلایل تخصیص و امتیاز
    blockers: Mapped[Optional[str]] = mapped_column(Text)         # JSON محدودیت‌های مانع

    __table_args__ = (Index("ix_opt_assign_run", run_id),)


class IdempotencyKey(PkMixin, Base):
    """Idempotency-Key برای عملیات حساس."""
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(120), unique=True)
    endpoint: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[Optional[str]] = mapped_column(String(64))
    response_status: Mapped[Optional[int]] = mapped_column(Integer)
    response_body: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UploadedFile(PkMixin, TsMixin, Base):
    __tablename__ = "uploaded_files"

    filename: Mapped[str] = mapped_column(String(300))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
