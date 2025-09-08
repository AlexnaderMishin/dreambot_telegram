import time, os, sys
import psycopg

url = os.getenv("DATABASE_URL")
if not url:
    print("DATABASE_URL not set", file=sys.stderr)
    sys.exit(1)

# psycopg не понимает драйверный префикс "+psycopg" (это для SQLAlchemy)
dsn = url.replace("+psycopg", "")

for i in range(60):
    try:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        print("DB is up")
        sys.exit(0)
    except Exception as e:
        print(f"DB not ready yet: {e}")
        time.sleep(2)

print("Timed out waiting for DB", file=sys.stderr)
sys.exit(2)

if not url:
    print("DATABASE_URL not set", file=sys.stderr)
    sys.exit(1)

for i in range(60):
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            print("DB is up")
            sys.exit(0)
    except Exception as e:
        print(f"DB not ready yet: {e}")
        time.sleep(2)

print("Timed out waiting for DB", file=sys.stderr)
sys.exit(2)
