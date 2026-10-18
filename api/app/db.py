import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@contextmanager
def get_conn():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        # pgvector lives in `extensions` on Supabase; keep local Docker working too.
        with conn.cursor() as cur:
            cur.execute("SET search_path TO public, extensions")
        yield conn


def ping_db() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
