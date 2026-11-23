from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "فضایار۳۶۰"
    app_desc: str = "زیرسیستم مدیریت و بهینه‌سازی فضاهای آموزشی در زیست‌بوم دانشجو۳۶۰"
    # استقرار عملیاتی: postgres در docker-compose
    database_url: str = "postgresql+psycopg2://fazayar:fazayar@db:5432/fazayar"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    timezone: str = "Asia/Tehran"
    demo_mode: bool = True          # در حالت دمو، همگام‌سازی آزمایشی پایه‌یار مجاز است
    seed_on_start: bool = True      # اگر پایگاه داده خالی بود، داده نمونه بسازد
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 5
    default_bookable_start: int = 7   # ساعت شروع مجاز پیش‌فرض
    default_bookable_end: int = 21    # ساعت پایان مجاز پیش‌فرض
    rate_limit_per_minute: int = 240
    cors_origins: str = "*"
    payehtar_base_url: str = ""       # آدرس API پایه‌یار۳۶۰ در استقرار واقعی
    dist_dir: str = ""                # مسیر dist فرانت‌اند (در Docker تنظیم می‌شود)

    # ورود یکپارچه سازمانی (SSO/OIDC) — در استقرار واقعی پر می‌شود
    sso_enabled: bool = False         # فعال‌سازی دکمهٔ ورود SSO در صفحهٔ لاگین
    sso_issuer: str = ""              # نشانی صادرکننده؛ مثلا https://sso.uni.ac.ir/realms/uni
    sso_client_id: str = ""
    sso_client_secret: str = ""
    sso_authorize_url: str = ""       # اگر خالی باشد از قالب استاندارد Keycloak ساخته می‌شود
    sso_token_url: str = ""           # اگر خالی باشد از قالب استاندارد Keycloak ساخته می‌شود
    sso_userinfo_url: str = ""        # اگر خالی باشد از قالب استاندارد Keycloak ساخته می‌شود
    sso_scopes: str = "openid profile email"
    sso_role_default: str = "student" # نقش کاربران تازهٔ SSO
    sso_admin_email: str = ""         # این ایمیل نقش sys_admin می‌گیرد

    model_config = {"env_file": ".env", "env_prefix": "FAZAYAR_"}


settings = Settings()
