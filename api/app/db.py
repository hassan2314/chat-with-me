from contextlib import contextmanager

import psycopg

from app.settings import database_url, db_connect_timeout


@contextmanager
def get_conn():
    # prepare_threshold=None keeps session state working through a transaction pooler.
    # search_path covers pgvector in `extensions` (Supabase) and in public (local Docker).
    with psycopg.connect(
        database_url(),
        connect_timeout=db_connect_timeout(),
        prepare_threshold=None,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO public, extensions")
            cur.execute("SET statement_timeout = '15s'")
        yield conn


def ping_db() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
