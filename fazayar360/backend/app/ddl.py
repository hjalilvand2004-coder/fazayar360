"""مهاجرت‌های خاص PostgreSQL که create_all نمی‌سازد — شامل قید قطعی عدم هم‌پوشانی بازه زمانی."""
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
            conn.execute(text(stmt))
