"""Apply a .sql file to the database using DATABASE_URL from .env.

Reads the SQL file as UTF-8 and executes it via psycopg, so non-ASCII content
(e.g. Thai province names) is handled correctly without shell-encoding issues.

Usage (from repo root):
  .venv\\Scripts\\python.exe scripts\\db_apply.py supabase\\migrations\\0001_heatwave_schema.sql
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env():
    path = os.path.join(REPO, ".env")
    if not os.path.exists(path):
        sys.exit(".env not found at repo root")
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: db_apply.py <path-to.sql>")
    load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL not set in .env")

    sql = open(sys.argv[1], encoding="utf-8").read()
    import psycopg  # noqa: E402

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print(f"applied {sys.argv[1]}")


if __name__ == "__main__":
    main()
