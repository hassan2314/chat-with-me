import os

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.chat import answer_question, stream_answer
from app.db import ping_db
from app.match_jd import match_job_description
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

SUGGESTIONS = [
    "Why should we hire Hassan?",
    "What’s your experience with NestJS?",
    "Tell me about production AI work.",
    "What’s the 50k-reader product?",
    "Where did you study?",
]


def cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    defaults = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ]
    return list(dict.fromkeys(origins + defaults))


def require_admin(x_admin_secret: str | None) -> None:
    expected = os.getenv("ADMIN_SECRET", "")
    if not expected or x_admin_secret != expected:
        raise HTTPException(status_code=401, detail="invalid admin secret")


app = FastAPI(title="Hassan Portfolio Chat API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_origin_regex=r"https://.*\.(netlify\.app|netlify\.com)",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        ping_db()
        db = "ok"
    except Exception:
        db = "error"
    return HealthResponse(api="ok", db=db)


@app.post("/v1/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    try:
        return ChatResponse(**answer_question(req.question.strip()))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_answer(req.question.strip()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/v1/match-jd", response_model=MatchJdResponse)
def match_jd(req: MatchJdRequest) -> MatchJdResponse:
    text = req.text()
    if not text:
        raise HTTPException(status_code=400, detail="job_description is required")
    try:
        return MatchJdResponse(**match_job_description(text))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/v1/suggestions", response_model=SuggestionsResponse)
def suggestions() -> SuggestionsResponse:
    return SuggestionsResponse(suggestions=SUGGESTIONS)


@app.post("/v1/seed", response_model=SeedResponse)
def seed(x_admin_secret: str | None = Header(default=None)) -> SeedResponse:
    require_admin(x_admin_secret)
    try:
        return SeedResponse(**run_seed())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/reset")
def reset(x_admin_secret: str | None = Header(default=None)) -> dict:
    require_admin(x_admin_secret)
    wipe()
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
