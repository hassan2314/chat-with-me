"""Environment settings. Values are read at call time so tests and hosts can override them."""

import os
import re

from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(ROOT, ".env"))

_HEX = re.compile(r"^#([0-9a-fA-F]{6})$")
_PLACEHOLDER_KEYS = {"", "your_gemini_api_key", "changeme", "change-me"}


class DatabaseConfigError(RuntimeError):
    """DATABASE_URL is missing. The message stays free of credentials."""


def _raw(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def gemini_api_key() -> str:
    return _raw("GEMINI_API_KEY") or _raw("GOOGLE_API_KEY")


def llm_mode() -> str:
    """auto uses Gemini when a real key is set, and the local composer otherwise."""
    mode = _raw("LLM_MODE", "auto").lower()
    if mode in {"mock", "local"}:
        return "mock"
    if mode == "gemini":
        return "gemini"
    key = gemini_api_key().lower()
    if key in _PLACEHOLDER_KEYS or key.startswith("your_"):
        return "mock"
    return "gemini"


def database_url() -> str:
    url = _raw("DATABASE_URL")
    if not url:
        raise DatabaseConfigError("DATABASE_URL is not set")
    if "supabase.co" in url and "sslmode=" not in url:
        join = "&" if "?" in url else "?"
        url = f"{url}{join}sslmode=require"
    return url


def db_connect_timeout() -> int:
    try:
        return max(1, min(int(_raw("DB_CONNECT_TIMEOUT", "5") or "5"), 30))
    except ValueError:
        return 5


def db_ready_wait() -> float:
    try:
        return max(0.0, min(float(_raw("DB_READY_WAIT_SECONDS", "8") or "8"), 30.0))
    except ValueError:
        return 8.0


def mock_stream_delay() -> float:
    try:
        millis = float(_raw("MOCK_STREAM_DELAY_MS", "16") or "16")
    except ValueError:
        millis = 16.0
    return max(0.0, min(millis, 200.0)) / 1000.0


def cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "")
    if raw.strip() == "*":
        return ["*"]
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    defaults = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ]
    return list(dict.fromkeys([*origins, *defaults]))


def cors_origin_regex() -> str | None:
    if cors_origins() == ["*"]:
        return None
    if "CORS_ORIGIN_REGEX" not in os.environ:
        return r"https://.*\.(netlify\.app|netlify\.com|fastapicloud\.dev)"
    raw = os.environ["CORS_ORIGIN_REGEX"].strip()
    return raw or None


def _http_origin(value: str, *, allow_path: bool = False) -> str | None:
    from urllib.parse import urlparse

    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    if not allow_path and parsed.path not in {"", "/"}:
        return None
    if not allow_path and (parsed.query or parsed.fragment):
        return None
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if not allow_path:
        return origin
    path = parsed.path or ""
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return origin + path


# Public chat the embed talks to. Override with PUBLIC_API_URL when the host changes.
DEFAULT_PUBLIC_API = "https://chat-with-me.fastapicloud.dev"


def http_origin(value: str) -> str | None:
    """Scheme and host only. A path or query is ignored. Userinfo is rejected."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def public_api_base() -> str:
    raw = _raw("PUBLIC_API_URL") or _raw("WIDGET_API_BASE") or DEFAULT_PUBLIC_API
    return http_origin(raw) or DEFAULT_PUBLIC_API


def portfolio_url() -> str:
    fallback = "https://genuine-kleicha-d80d7d.netlify.app"
    return _http_origin(_raw("PORTFOLIO_URL", fallback), allow_path=True) or fallback


def _clip(value: str, default: str, limit: int) -> str:
    cleaned = re.sub(r"[\x00-\x1f<>]", "", value).strip()
    cleaned = cleaned[:limit].strip()
    return cleaned or default


def widget_branding(
    title: str | None = None,
    subtitle: str | None = None,
    placeholder: str | None = None,
    accent: str | None = None,
) -> dict[str, str]:
    defaults = {
        "title": _clip(_raw("WIDGET_TITLE", "Ask Hassan"), "Ask Hassan", 48),
        "subtitle": _clip(
            _raw("WIDGET_SUBTITLE", "Questions about my work"),
            "Questions about my work",
            80,
        ),
        "placeholder": _clip(
            _raw("WIDGET_PLACEHOLDER", "Ask about a role, a stack, or a project"),
            "Ask about a role, a stack, or a project",
            80,
        ),
        "accent": "#0f5c45",
    }
    chosen = (accent or _raw("WIDGET_ACCENT", "")).strip()
    if _HEX.fullmatch(chosen):
        defaults["accent"] = chosen.lower()
    if title is not None:
        defaults["title"] = _clip(title, defaults["title"], 48)
    if subtitle is not None:
        defaults["subtitle"] = _clip(subtitle, defaults["subtitle"], 80)
    if placeholder is not None:
        defaults["placeholder"] = _clip(placeholder, defaults["placeholder"], 80)
    return defaults
