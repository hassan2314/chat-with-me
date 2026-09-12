from google.genai import types

from app.chat import CHAT_MODEL, citations_from
from app.rag import gemini, search

SYSTEM = """You compare a job description to Hassan Ahmed’s retrieved career records.
Be honest. Do not invent skills or jobs.

Return short markdown with these headings:
- Strong overlap
- Related
- Not on record
- Evidence (company / project + stack)
- CTA (email hassan87691@gmail.com and the portfolio)

If the JD asks for something absent from the records, list it under Not on record.
"""


def match_job_description(jd: str) -> dict:
    rows = search(jd, categories=["experience", "skill", "project"], k=10)
    context = "\n\n---\n\n".join(
        f"[{row['category']}] {row['title']}\n{row['content']}" for row in rows
    ) or "(no records)"
    prompt = f"Job description:\n{jd}\n\nHassan’s records:\n{context}"
    response = gemini().models.generate_content(
        model=CHAT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            temperature=0.2,
        ),
    )
    return {
        "summary": (response.text or "").strip() or "No comparison generated.",
        "citations": citations_from(rows),
    }
