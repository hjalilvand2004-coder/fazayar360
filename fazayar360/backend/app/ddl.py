"""مهاجرت‌های خاص PostgreSQL که create_all نمی‌سازد — شامل قید قطعی عدم هم‌پوشانی بازه زمانی.

هر دستور جداگانه اجرا می‌شود؛ اگر افزونه/قید در محیط مقصد در دسترس نباشد (مثل برخی بسته‌های
پرتیبل)، سامانه با خطای هشدار ادامه می‌دهد و جلوگیری از رزرو متعارض بر عهده قفل تراکنشی
ردیف فضا در سرویس تأیید باقی می‌ماند.
"""
import logging

log = logging.getLogger("fazayar.ddl")

POSTGRES_EXTRAS = [
    "CREATE EXTENSION IF NOT EXISTS btree_gist",
    # مقدار پیش‌فرض زمان برای جدول کلیدهای idempotency (سازگار با نصب‌های قبلی)
    "ALTER TABLE idempotency_keys ALTER COLUMN created_at SET DEFAULT now()",
    # جلوگیری قطعی از تخصیص هم‌زمان دو رزرو متعارض برای یک فضا (بازه مؤثر شامل آماده‌سازی/پاک‌سازی)
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'excl_space_active_period') THEN
            ALTER TABLE resource_allocations
            ADD CONSTRAINT excl_space_active_period
            EXCLUDE USING gist (
                space_id WITH =,
                tstzrange(effective_start, effective_end, '[)') WITH &&
            ) WHERE (status = 'active');
        END IF;
    END $$;
    """,
]


def apply_postgres_extras(engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    from sqlalchemy import text
    with engine.begin() as conn:
        for stmt in POSTGRES_EXTRAS:
            try:
                conn.execute(text(stmt))
            except Exception as e:  # noqa: BLE001
                log.warning("اجرای مهاجرت‌های دیتابیس کامل نشد (سامانه با کنترل تراکنشی ادامه می‌دهد): %s", e.__class__.__name__)
