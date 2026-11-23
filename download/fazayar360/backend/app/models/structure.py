import uuid
from datetime import time
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, PkMixin, TsMixin
from .enums import SpaceStatus, SpaceType


class Campus(PkMixin, TsMixin, Base):
    __tablename__ = "campuses"

    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    buildings: Mapped[list["Building"]] = relationship(back_populates="campus")


class Building(PkMixin, TsMixin, Base):
    __tablename__ = "buildings"

    campus_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campuses.id"))
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[Optional[str]] = mapped_column(String(500))
    responsible_unit: Mapped[Optional[str]] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    campus: Mapped[Campus] = relationship(back_populates="buildings")
    floors: Mapped[list["Floor"]] = relationship(back_populates="building", order_by="Floor.number")

    __table_args__ = (Index("ix_buildings_campus", campus_id),)


class Floor(PkMixin, TsMixin, Base):
    __tablename__ = "floors"

    building_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buildings.id"))
    number: Mapped[int] = mapped_column(Integer)
    name: Mapped[Optional[str]] = mapped_column(String(100))

    building: Mapped[Building] = relationship(back_populates="floors")
    spaces: Mapped[list["Space"]] = relationship(back_populates="floor")

    __table_args__ = (Index("ix_floors_building", building_id),)


class Space(PkMixin, TsMixin, Base):
    """شناسنامه جامع فضا."""
    __tablename__ = "spaces"

    code: Mapped[str] = mapped_column(String(50), unique=True)      # کد فضا (مثل BR-1-204)
    name: Mapped[str] = mapped_column(String(200))
    space_type: Mapped[str] = mapped_column(String(40), default=SpaceType.general_classroom.value)
    status: Mapped[str] = mapped_column(String(30), default=SpaceStatus.active.value)

    campus_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campuses.id"))
    building_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buildings.id"))
    floor_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("floors.id"))

    area_m2: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    safe_capacity: Mapped[Optional[int]] = mapped_column(Integer)   # ظرفیت ایمن
    description: Mapped[Optional[str]] = mapped_column(Text)
    responsible_unit: Mapped[Optional[str]] = mapped_column(String(200))   # واحد متولی
    responsible_person: Mapped[Optional[str]] = mapped_column(String(200)) # مسئول پاسخ‌گو
    responsible_contact: Mapped[Optional[str]] = mapped_column(String(200))

    # دسترس‌پذیری
    has_step_free_access: Mapped[bool] = mapped_column(Boolean, default=False)  # مسیر بدون پله
    has_elevator_access: Mapped[bool] = mapped_column(Boolean, default=False)
    accessibility_notes: Mapped[Optional[str]] = mapped_column(Text)

    # شرایط استفاده
    needs_lab_manager: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_group_names: Mapped[Optional[str]] = mapped_column(String(500))  # گروه‌های مجاز، جدا با کاما
    min_prep_minutes: Mapped[int] = mapped_column(Integer, default=0)   # زمان آماده‌سازی
    min_cleanup_minutes: Mapped[int] = mapped_column(Integer, default=0)  # زمان پاک‌سازی

    # محدودسازی دسترسی حوزه‌ای (اختیاری): اگر ست شد فقط این دانشکده/گروه
    owner_faculty: Mapped[Optional[str]] = mapped_column(String(200))

    # نقشه طبقات (نمای دوبعدی)
    map_x: Mapped[Optional[int]] = mapped_column(Integer)
    map_y: Mapped[Optional[int]] = mapped_column(Integer)
    map_w: Mapped[Optional[int]] = mapped_column(Integer, default=120)
    map_h: Mapped[Optional[int]] = mapped_column(Integer, default=80)

    image_file_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    docs: Mapped[Optional[str]] = mapped_column(Text)          # JSON: فایل‌ها/لینک‌ها
    public_slug: Mapped[str] = mapped_column(String(64), unique=True)  # برای QR

    version: Mapped[int] = mapped_column(Integer, default=1)   # کنترل نسخه رکورد

    floor: Mapped[Optional[Floor]] = relationship(back_populates="spaces")
    building: Mapped[Building] = relationship()
    campus: Mapped[Campus] = relationship()
    layouts: Mapped[list["SpaceLayout"]] = relationship(back_populates="space", cascade="all, delete-orphan")
    space_features: Mapped[list["SpaceFeature"]] = relationship(back_populates="space", cascade="all, delete-orphan")
    availability_rules: Mapped[list["AvailabilityRule"]] = relationship(back_populates="space", cascade="all, delete-orphan")
    space_equipment: Mapped[list["SpaceEquipment"]] = relationship(back_populates="space", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_spaces_building", building_id),
        Index("ix_spaces_type_status", space_type, status),
    )


class SpaceLayout(PkMixin, TsMixin, Base):
    """چیدمان و ظرفیت مجاز در هر چیدمان — ظرفیت عدد ثابت مبهم نیست."""
    __tablename__ = "space_layouts"

    space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spaces.id"))
    name: Mapped[str] = mapped_column(String(100))       # سخنرانی / کارگاهی / آزمون / مدارگرد
    capacity: Mapped[int] = mapped_column(Integer)
    seats_count: Mapped[Optional[int]] = mapped_column(Integer)
    tables_count: Mapped[Optional[int]] = mapped_column(Integer)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    space: Mapped[Space] = relationship(back_populates="layouts")

    __table_args__ = (Index("ix_space_layouts_space", space_id),)


class Feature(PkMixin, TsMixin, Base):
    """فرهنگ ویژگی‌ها (امکانات)."""
    __tablename__ = "features"

    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50), default="general")  # display/board/network/power/specialized/other
    icon: Mapped[Optional[str]] = mapped_column(String(50))


class SpaceFeature(PkMixin, Base):
    __tablename__ = "space_features"

    space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spaces.id"))
    feature_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("features.id"))
    condition: Mapped[str] = mapped_column(String(30), default="active")  # active | broken
    note: Mapped[Optional[str]] = mapped_column(String(300))

    space: Mapped[Space] = relationship(back_populates="space_features")
    feature: Mapped[Feature] = relationship()

    __table_args__ = (Index("ix_space_features_space", space_id),)


class AvailabilityRule(PkMixin, TsMixin, Base):
    """قواعد ساعات مجاز — weekday با شماره‌گذاری فارسی: ۰=شنبه … ۶=جمعه."""
    __tablename__ = "availability_rules"

    space_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("spaces.id"))  # null = قاعده پیش‌فرض سراسری
    weekday: Mapped[int] = mapped_column(Integer)          # 0=شنبه
    start_time: Mapped[time] = mapped_column()
    end_time: Mapped[time] = mapped_column()
    is_bookable: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_from: Mapped[Optional[str]] = mapped_column(String(10))   # تاریخ میلادی YYYY-MM-DD
    valid_to: Mapped[Optional[str]] = mapped_column(String(10))

    space: Mapped[Space] = relationship(back_populates="availability_rules")

    __table_args__ = (Index("ix_availability_space", space_id, weekday),)
