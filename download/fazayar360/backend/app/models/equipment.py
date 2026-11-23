import uuid
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, PkMixin, TsMixin

if TYPE_CHECKING:
    from .structure import Space


class EquipmentType(PkMixin, TsMixin, Base):
    __tablename__ = "equipment_types"

    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(30), default="fixed")  # fixed | portable | consumable
    default_lead_minutes: Mapped[int] = mapped_column(Integer, default=0)  # زمان آماده‌سازی تجهیز

    assets: Mapped[list["EquipmentAsset"]] = relationship(back_populates="type")


class EquipmentAsset(PkMixin, TsMixin, Base):
    """تجهیز دارای شناسه مستقل (ثابت یا قابل‌حمل)."""
    __tablename__ = "equipment_assets"

    type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment_types.id"))
    asset_tag: Mapped[Optional[str]] = mapped_column(String(100))   # کد اموال مرجع
    name: Mapped[str] = mapped_column(String(200))
    model: Mapped[Optional[str]] = mapped_column(String(200))
    serial_number: Mapped[Optional[str]] = mapped_column(String(200))
    location_space_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))  # محل استقرار
    status: Mapped[str] = mapped_column(String(30), default="operational")
    last_service_date: Mapped[Optional[date]] = mapped_column(Date)
    next_calibration_due: Mapped[Optional[date]] = mapped_column(Date)  # اعتبار کالیبراسیون
    usage_restriction: Mapped[Optional[str]] = mapped_column(Text)
    responsible_person: Mapped[Optional[str]] = mapped_column(String(200))
    docs: Mapped[Optional[str]] = mapped_column(Text)               # JSON دستورالعمل/مستندات
    bookable_independently: Mapped[bool] = mapped_column(Boolean, default=False)

    type: Mapped[EquipmentType] = relationship(back_populates="assets")


class EquipmentPool(PkMixin, TsMixin, Base):
    """تجهیزات شمارشی مشابه (مثل ۲۰ لپ‌تاپ یک مدل) — رزرو با تعداد."""
    __tablename__ = "equipment_pools"

    type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment_types.id"))
    name: Mapped[str] = mapped_column(String(200))
    home_space_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    total_quantity: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="operational")

    type: Mapped[EquipmentType] = relationship()


class SpaceEquipment(PkMixin, Base):
    """ارتباط فضا و تجهیز؛ برای تجهیزات شمارشی، ظرفیت تجهیزاتی فضا را می‌سازد."""
    __tablename__ = "space_equipment"

    space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spaces.id"))
    type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment_types.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    per_unit_capacity: Mapped[Optional[int]] = mapped_column(Integer)  # مثل ۱۲ ایستگاه × ۲ نفر = ۲۴
    is_broken: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[Optional[str]] = mapped_column(String(300))

    space: Mapped["Space"] = relationship(back_populates="space_equipment")
    type: Mapped[EquipmentType] = relationship()
