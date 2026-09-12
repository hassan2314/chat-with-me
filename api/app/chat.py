import json
import os
from collections.abc import Iterator

from google.genai import types

from app.classify import classify
from app.db import get_conn
from app.rag import gemini, search

SITE = os.getenv(
    "PORTFOLIO_URL",
    "https://genuine-kleicha-d80d7d.netlify.app",
).rstrip("/")

ANCHORS = {
    "about": "#contact",
    "education": "#education",
    "experience": "#experience",
    "skill": "#skills",
    "project": "#projects",
}

CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-3.6-flash")

SYSTEM = """You are Hassan Ahmed’s portfolio assistant for recruiters.
Speak as Hassan in first person, short paragraphs, concrete evidence.

Always prefer: company, role, dates, stack, outcome (users, modules, billing, OCR).
Never invent employers, titles, or metrics.
If the question is a hiring pitch, lead with production ownership
(ReadMaududi 50k+ readers, NestJS/Next.js, AI in production APIs),
then 2 proof points, then contact.

Answer only from the retrieved records.
If nothing relevant is in the records, say you do not have that on record
and point to hassan87691@gmail.com.
End useful answers with a brief contact CTA when it fits.
"""

FOLLOWUPS = {
    "about": [
        "Why should we hire Hassan?",
        "Are you open to new roles?",
    ],
    "experience": [
        "What’s your experience with NestJS?",
        "Tell me about ReadMaududi.",
    ],
    "project": [
        "Which projects are in production?",
        "What did you build in the Acme Docs Copilot?",
    ],
    "skill": [
        "Where have you used PostgreSQL in production?",
        "What AI integrations have you shipped?",
    ],
    "education": [
        "What was your final year project?",
        "Which internships did you complete?",
    ],
}


def citations_from(rows: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for row in rows:
        key = (row["category"], row["title"])
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "category": row["category"],
                "title": row["title"],
                "anchor": f"{SITE}/{ANCHORS.get(row['category'], '')}",
                "score": round(row["score"], 4),
            }
        )
    return out


def _followups(categories: list[str] | None) -> list[str]:
    cats = categories or ["about", "experience", "project"]
    picked: list[str] = []
    for cat in cats:
        for item in FOLLOWUPS.get(cat, []):
            if item not in picked:
                picked.append(item)
            if len(picked) >= 3:
                return picked
    return picked


def _log(question: str, categories: list[str] | None) -> None:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO chat_logs (question, categories) VALUES (%s, %s)",
                    (question, categories or []),
                )
            conn.commit()
    except Exception:
        pass


EMPTY_ANSWER = (
    "I don’t have that on record yet. "
    "Email hassan87691@gmail.com or see the contact section on my portfolio."
)


def _prompt(question: str, rows: list[dict]) -> str:
    context = "\n\n---\n\n".join(
        f"[{row['category']}] {row['title']}\n{row['content']}" for row in rows
    )
    return (
        f"Question: {question}\n\n"
        f"Records:\n{context}\n\n"
        "Answer the question using only these records."
    )


def _gen_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=SYSTEM,
        temperature=0.3,
    )


def _chunk_text(chunk) -> str:
    try:
        return chunk.text or ""
    except Exception:
        return ""


def _retrieve(question: str) -> tuple[list[str] | None, list[dict]]:
    categories = classify(question)
    rows = search(question, categories)
    _log(question, categories)
    return categories, rows


def _meta(categories: list[str] | None, rows: list[dict]) -> dict:
    return {
        "citations": citations_from(rows),
        "suggested_followups": _followups(categories),
        "categories": categories,
    }


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _generate(question: str, rows: list[dict]) -> str:
    if not rows:
        return EMPTY_ANSWER

    response = gemini().models.generate_content(
        model=CHAT_MODEL,
        contents=_prompt(question, rows),
        config=_gen_config(),
    )
    text = (response.text or "").strip()
    return text or (
        "I could not form an answer from the records. "
        "Email hassan87691@gmail.com."
    )


def answer_question(question: str) -> dict:
    categories, rows = _retrieve(question)
    return {
        "answer": _generate(question, rows),
        **_meta(categories, rows),
    }


def stream_answer(question: str) -> Iterator[str]:
    try:
        categories, rows = _retrieve(question)
        yield _sse("meta", _meta(categories, rows))
        if not rows:
            yield _sse("token", {"t": EMPTY_ANSWER})
            yield _sse("done", {})
            return

        for chunk in gemini().models.generate_content_stream(
            model=CHAT_MODEL,
            contents=_prompt(question, rows),
            config=_gen_config(),
        ):
            text = _chunk_text(chunk)
            if text:
                yield _sse("token", {"t": text})
        yield _sse("done", {})
    except Exception as exc:
        yield _sse("error", {"detail": str(exc)})
        yield _sse("done", {})
