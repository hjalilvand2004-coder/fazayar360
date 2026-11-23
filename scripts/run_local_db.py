"""اجرای محلی PostgreSQL با pgserver (بدون نیاز به نصب PostgreSQL در سیستم).

استفاده:
  python run_local_db.py [مسیر_داده] --hold
  • مسیر_داده: دایرکتوری داده PostgreSQL (پیش‌فرض: /home/z/my-project/.pgdata-fazayar)
  • --hold: فرایند زنده می‌ماند تا سرور روشن بماند
خروجی: DATABASE_URL سازگار با SQLAlchemy روی stdout
"""
import sys
import time

import pgserver

DEFAULT_DATA_DIR = "/home/z/my-project/.pgdata-fazayar"


def main():
    args = [a for a in sys.argv[1:] if a != "--hold"]
    data_dir = args[0] if args else DEFAULT_DATA_DIR
    db = pgserver.get_server(data_dir)
    uri = db.get_uri()
    sa_url = uri.replace("postgresql://", "postgresql+psycopg2://")
    print(sa_url, flush=True)
    if "--hold" in sys.argv:
        print("HOLDING", flush=True)
        while True:
            time.sleep(3600)
    return 0


if __name__ == "__main__":
    sys.exit(main())
