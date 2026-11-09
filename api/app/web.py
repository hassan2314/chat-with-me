"""Browser pages: a chat home, an embeddable frame, and the loader script."""

import json
from html import escape
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from app.settings import http_origin, portfolio_url, public_api_base, widget_branding

STATIC = Path(__file__).resolve().parent / "static"
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
PAGE = (STATIC / "page.html").read_text(encoding="utf-8")


def _origin(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    return http_origin(str(value))


def _config(request: Request, layout: str) -> dict[str, str]:
    params = request.query_params
    branding = widget_branding(
        title=params.get("title"),
        subtitle=params.get("subtitle"),
        placeholder=params.get("placeholder"),
        accent=params.get("accent"),
    )
    override = _origin(params.get("api"))
    if layout == "embed":
        api_base = override or public_api_base()
    else:
        # The home page talks to the API it was served from, unless ?api= is set.
        api_base = override or ""
    return {
        "apiBase": api_base,
        "layout": layout,
        "portfolioUrl": portfolio_url(),
        **branding,
    }


def _html(layout: str, config: dict[str, str]) -> HTMLResponse:
    payload = json.dumps(config, ensure_ascii=False).replace("<", "\\u003c")
    title = "Ask Hassan" if layout == "embed" else "Hassan Ahmed · Portfolio chat"
    page = (
        PAGE.replace("__LAYOUT__", layout)
        .replace("__TITLE__", title)
        .replace("__PORTFOLIO__", escape(config["portfolioUrl"], quote=True))
        .replace("__CONFIG__", payload)
    )
    headers = {"Cache-Control": "no-cache"}
    if layout == "embed":
        headers["Content-Security-Policy"] = "frame-ancestors *"
    return HTMLResponse(page, headers=headers)


def register_pages(app: FastAPI) -> None:
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        return _html("page", _config(request, "page"))

    @app.get("/embed", response_class=HTMLResponse)
    def embed(request: Request) -> HTMLResponse:
        return _html("embed", _config(request, "embed"))

    @app.get("/widget.js")
    def widget_js() -> Response:
        script = (STATIC / "widget.js").read_text(encoding="utf-8")
        prelude = (
            f"var PORTFOLIO_API_BASE = {json.dumps(public_api_base())};\n"
        )
        return Response(
            prelude + script,
            media_type="application/javascript",
            headers={"Cache-Control": "public, max-age=300"},
        )

    @app.get("/favicon.svg")
    def favicon() -> Response:
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" rx="7" fill="#0f5c45"/>
<text x="16" y="21" text-anchor="middle" font-family="Georgia,serif" font-size="13" fill="#f6f1e7">HA</text>
</svg>"""
        return Response(svg, media_type="image/svg+xml")

    @app.get("/examples/embed.html", response_class=HTMLResponse)
    def embed_example() -> HTMLResponse:
        path = EXAMPLES / "embed.html"
        if not path.is_file():
            return HTMLResponse("<p>Example page is missing.</p>", status_code=404)
        return HTMLResponse(
            path.read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-cache"},
        )
