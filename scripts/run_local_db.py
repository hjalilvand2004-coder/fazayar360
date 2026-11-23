"""اجرای محلی PostgreSQL با pgserver.

حالت ۱: python run_local_db.py          → شروع سرور، چاپ DATABASE_URL و خروج
حالت ۲: python run_local_db.py --hold   → سرور روشن می‌ماند تا فرایند زنده است
"""
import sys
import time

import pgserver

DATA_DIR = "/home/z/my-project/.pgdata-fazayar"


def main():
    db = pgserver.get_server(DATA_DIR)
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
