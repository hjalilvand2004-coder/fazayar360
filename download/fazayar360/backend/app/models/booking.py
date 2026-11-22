import uuid
from datetime import datetime, time
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, PkMixin, TsMixin


class BookingRequest(PkMixin, TsMixin, Base):
    """درخواست استفاده از فضا؛ وضعیت درخواست از وضعیت اشغال فضا جداست."""
    __tablename__ = "booking_requests"

    request_number: Mapped[str] = mapped_column(String(30), unique=True)
    requester_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    use_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="draft")

    course_offer_ref: Mapped[Optional[str]] = mapped_column(String(100))  # شناسه ارائه درس در زیست‌بوم
    expected_attendees: Mapped[int] = mapped_column(Integer, default=0)
    enrollment_count: Mapped[Optional[int]] = mapped_column(Integer)      # تعداد ثبت‌نام دریافتی از زیرسیستم آموزش

    required_feature_ids: Mapped[Optional[str]] = mapped_column(Text)     # JSON آرایه uuid
    required_equipment_type_ids: Mapped[Optional[str]] = mapped_column(Text)  # JSON آرایه uuid
    layout_requested: Mapped[Optional[str]] = mapped_column(String(100))
    accessibility_required: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_lab_manager: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_campus_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    preferred_building_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))

    requested_space_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("spaces.id"))  # فضای درخواستی
    portable_needs: Mapped[Optional[str]] = mapped_column(Text)  # JSON [{type_id, quantity}] تجهیزات قابل‌حمل
    decision_note: Mapped[Optional[str]] = mapped_column(Text)
    decided_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text)

    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    occurrences: Mapped[list["BookingOccurrence"]] = relationship(back_populates="request", cascade="all, delete-orphan")
    series: Mapped[Optional["BookingSeries"]] = relationship(back_populates="request", uselist=False, cascade="all, delete-orphan")
    allocations: Mapped[list["ResourceAllocation"]] = relationship(back_populates="request")

    __table_args__ = (Index("ix_booking_requests_status", status),)


class BookingSeries(PkMixin, Base):
    """الگوی جلسات تکرارشونده — به رخدادهای تاریخ‌دار تبدیل می‌شود."""
    __tablename__ = "booking_series"

    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("booking_requests.id"))
    weekday: Mapped[int] = mapped_column(Integer)          # 0=شنبه
    start_time: Mapped[time] = mapped_column()
    end_time: Mapped[time] = mapped_column()
    start_date: Mapped[str] = mapped_column(String(10))    # YYYY-MM-DD
    end_date: Mapped[str] = mapped_column(String(10))
    pattern: Mapped[str] = mapped_column(String(20), default="weekly")

    request: Mapped[BookingRequest] = relationship(back_populates="series")


class BookingOccurrence(PkMixin, TsMixin, Base):
    """جلسه تاریخ‌دار — واحد مدیریت استثناها (تعطیلی، جابه‌جایی یک جلسه)."""
    __tablename__ = "booking_occurrences"

    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("booking_requests.id"))
    series_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("booking_series.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="scheduled")  # scheduled|executed|cancelled|moved|no_show
    exception_note: Mapped[Optional[str]] = mapped_column(String(300))

    request: Mapped[BookingRequest] = relationship(back_populates="occurrences")
    allocations: Mapped[list["ResourceAllocation"]] = relationship(back_populates="occurrence")

    __table_args__ = (
        Index("ix_occurrences_start", start_at),
        Index("ix_occurrences_request", request_id),
    )


class ResourceAllocation(PkMixin, TsMixin, Base):
    """تخصیص قطعی فضا — مرجع واحد تقویم اشغال؛ قید EXCLUDE در PostgreSQL تداخل را قطعاً می‌بندد."""
    __tablename__ = "resource_allocations"

    space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spaces.id"))
    request_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("booking_requests.id"))
    occurrence_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("booking_occurrences.id"))
    block_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(30), default="booking")   # booking|maintenance|hold
    status: Mapped[str] = mapped_column(String(30), default="active")  # active|released
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # شامل آماده‌سازی
    effective_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))    # شامل پاک‌سازی
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    note: Mapped[Optional[str]] = mapped_column(String(300))

    request: Mapped[Optional[BookingRequest]] = relationship(back_populates="allocations")
    occurrence: Mapped[Optional[BookingOccurrence]] = relationship(back_populates="allocations")

    __table_args__ = (
        Index("ix_allocations_space_time", space_id, effective_start, effective_end),
        Index("ix_allocations_status", status),
    )


class EquipmentAllocation(PkMixin, TsMixin, Base):
    """تخصیص تجهیز (دارایی مستقل یا از استخر شمارشی) برای یک تخصیص فضا."""
    __tablename__ = "equipment_allocations"

    allocation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resource_allocations.id"))
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("equipment_assets.id"))
    pool_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("equipment_pools.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="active")  # active|released

    __table_args__ = (Index("ix_equipment_alloc_pool", pool_id, status),)


class ApprovalAction(PkMixin, Base):
    """تاریخچه تأیید و رد."""
    __tablename__ = "approval_actions"

    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("booking_requests.id"))
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    action: Mapped[str] = mapped_column(String(30))  # submit|review|approve|reject|cancel|move|reinstate
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MaintenanceBlock(PkMixin, TsMixin, Base):
    """انسداد تعمیراتی/آماده‌سازی و گزارش خرابی."""
    __tablename__ = "maintenance_blocks"

    space_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("spaces.id"))
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("equipment_assets.id"))
    reason_code: Mapped[str] = mapped_column(String(30), default="repair")
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[Optional[str]] = mapped_column(Text)
    reporter_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    reporter_name: Mapped[Optional[str]] = mapped_column(String(200))   # برای گزارش عمومی QR بدون احراز هویت
    status: Mapped[str] = mapped_column(String(30), default="active")   # reported|active|resolved|rejected
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolver_note: Mapped[Optional[str]] = mapped_column(String(300))


class UsageObservation(PkMixin, TsMixin, Base):
    """شواهد استفاده واقعی — داده مشاهده‌شده، جدا از داده استنباط‌شده."""
    __tablename__ = "usage_observations"

    space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spaces.id"))
    occurrence_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("booking_occurrences.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_headcount: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(30), default="manual")  # manual|sensor|qr_report
    observer_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    note: Mapped[Optional[str]] = mapped_column(String(300))
