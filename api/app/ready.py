"""Apply the schema off the request path so a slow database cannot block the port."""

import logging
import threading
import time

from app.db import ping_db
from app.migrate import apply_schema
from app.settings import DatabaseConfigError, db_connect_timeout

log = logging.getLogger("portfolio.ready")


class ReadyState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.schema = False
        self.db = "starting"
        self.attempts = 0
        self._started = False

    def snapshot(self) -> dict[str, str | int]:
        with self._lock:
            return {
                "schema_status": "ok" if self.schema else "pending",
                "db": self.db,
                "attempts": self.attempts,
            }

    def schema_ready(self) -> bool:
        with self._lock:
            return self.schema

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
        threading.Thread(target=self._run, name="schema-migrate", daemon=True).start()

    def wait(self, timeout: float) -> bool:
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            if self.schema_ready():
                return True
            if time.monotonic() >= deadline:
                return self.schema_ready()
            time.sleep(0.15)

    def _run(self) -> None:
        delay = 0.4
        while not self.schema_ready():
            self._attempt()
            if self.schema_ready():
                return
            time.sleep(delay)
            delay = min(delay * 2, 15)

    def _attempt(self) -> None:
        try:
            apply_schema()
            ping_db()
        except DatabaseConfigError:
            self._mark(db="unconfigured")
            return
        except Exception as exc:
            # Exception text from the driver can include the connection string.
            log.warning(
                "database not ready (connect_timeout=%ss): %s",
                db_connect_timeout(),
                exc.__class__.__name__,
            )
            self._mark(db="error")
            return
        with self._lock:
            self.schema = True
            self.db = "ok"
        log.info("database schema ready")

    def _mark(self, db: str) -> None:
        with self._lock:
            self.attempts += 1
            self.schema = False
            self.db = "starting" if db == "error" and self.attempts < 2 else db


ready = ReadyState()
