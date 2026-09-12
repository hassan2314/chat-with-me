"""FastAPI Cloud looks here (repo root) for a default app file."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "api"))

from app.main import app

__all__ = ["app"]
