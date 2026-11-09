import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.chat import answer_question, stream_answer
from app.match_jd import match_job_description
from app.ready import ready
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MatchJdRequest,
    MatchJdResponse,
    SeedResponse,
    SuggestionsResponse,
)
from app.seed import run_seed, wipe
from app.settings import cors_origin_regex, cors_origins, db_ready_wait, llm_mode
from app.web import register_pages

log = logging.getLogger("portfolio")

SUGGESTIONS = [
    "Why should we hire Hassan?",
    "What’s your experience with NestJS?",
    "Tell me about production AI work.",
    "What’s the 50k-reader product?",
    "Where did you study?",
]


def require_admin(x_admin_secret: str | None) -> None:
    expected = os.getenv("ADMIN_SECRET", "")
    if not expected or x_admin_secret != expected:
        raise HTTPException(status_code=401, detail="invalid admin secret")


def _question(raw: str) -> str:
    question = raw.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    return question


def _ensure_ready() -> None:
    if ready.wait(db_ready_wait()):
        return
    raise HTTPException(
        status_code=503,
        detail="The database is still starting. Try again in a moment.",
        headers={"Retry-After": "5"},
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Bind the port before Postgres answers. Supabase and other free databases
    # can take a while to wake; a blocking migrate here gets the process killed.
    logging.getLogger("portfolio").setLevel(logging.INFO)
    ready.start()
    yield


app = FastAPI(title="Hassan Portfolio Chat API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_origin_regex=cors_origin_regex(),
    allow_methods=["*"],
    allow_headers=["*"],
)
register_pages(app)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    state = ready.snapshot()
    return HealthResponse(
        api="ok",
        db=str(state["db"]),
        schema_status=str(state["schema_status"]),
        llm=llm_mode(),
    )


@app.post("/v1/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    _ensure_ready()
    try:
        return ChatResponse(**answer_question(_question(req.question)))
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("chat failed: %s", exc.__class__.__name__)
        raise HTTPException(
            status_code=503,
            detail="The assistant could not answer just now.",
        ) from exc


@app.post("/v1/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    _ensure_ready()
    question = _question(req.question)
    return StreamingResponse(
        stream_answer(question),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/v1/match-jd", response_model=MatchJdResponse)
def match_jd(req: MatchJdRequest) -> MatchJdResponse:
    _ensure_ready()
    text = req.text()
    if not text:
        raise HTTPException(status_code=400, detail="job_description is required")
    try:
        return MatchJdResponse(**match_job_description(text))
    except Exception as exc:
        log.warning("match-jd failed: %s", exc.__class__.__name__)
        raise HTTPException(
            status_code=503,
            detail="The assistant could not compare that description just now.",
        ) from exc


@app.get("/v1/suggestions", response_model=SuggestionsResponse)
def suggestions() -> SuggestionsResponse:
    return SuggestionsResponse(suggestions=SUGGESTIONS)


@app.post("/v1/seed", response_model=SeedResponse)
def seed(x_admin_secret: str | None = Header(default=None)) -> SeedResponse:
    require_admin(x_admin_secret)
    _ensure_ready()
    try:
        return SeedResponse(**run_seed())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail="seed file is missing") from exc
    except Exception as exc:
        log.warning("seed failed: %s", exc.__class__.__name__)
        raise HTTPException(
            status_code=503,
            detail="Seeding failed. Check the server logs.",
        ) from exc


@app.post("/v1/reset")
def reset(x_admin_secret: str | None = Header(default=None)) -> dict:
    require_admin(x_admin_secret)
    _ensure_ready()
    try:
        wipe()
    except Exception as exc:
        log.warning("reset failed: %s", exc.__class__.__name__)
        raise HTTPException(status_code=503, detail="Reset failed.") from exc
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
