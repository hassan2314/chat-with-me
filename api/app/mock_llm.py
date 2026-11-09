"""Local answers for demos without a Gemini key.

Retrieval ranks the stored portfolio rows in Python. Generation only rewrites
those rows into first person. It does not add employers, dates, or metrics.
"""

import re

from app.db import get_conn

STOP = {
    "a",
    "an",
    "and",
    "are",
    "about",
    "did",
    "do",
    "does",
    "for",
    "how",
    "i",
    "in",
    "is",
    "me",
    "my",
    "of",
    "on",
    "or",
    "the",
    "to",
    "tell",
    "what",
    "whats",
    "what's",
    "what’s",
    "with",
    "you",
    "your",
    "should",
    "we",
    "why",
}

_SPEAK = (
    (r"^Build and own\b", "I build and own"),
    (r"^Building\b", "I am building"),
    (r"^Developed\b", "I developed"),
    (r"^Architected\b", "I architected"),
    (r"^Implemented\b", "I implemented"),
    (r"^Integrated\b", "I integrated"),
    (r"^Optimized\b", "I optimized"),
    (r"^Contributed\b", "I contributed"),
    (r"^Own the\b", "I own the"),
)

_PERSON = (
    (r"\bHire Hassan\b", "Hire me"),
    (r"\bHassan Ahmed's\b", "My"),
    (r"\bHassan Ahmed is\b", "I am"),
    (r"\bHassan Ahmed\b", "I"),
    (r"\bHe builds\b", "I build"),
    (r"\bHe owns\b", "I own"),
    (r"\bhe owns\b", "I own"),
    (r"\bHe also\b", "I also"),
    (r"\bhe also\b", "I also"),
    (r"\bHe already\b", "I already"),
    (r"\bHis\b", "My"),
    (r"\bhis\b", "my"),
    (r"\bHe\b", "I"),
    (r"\bhe\b", "I"),
)

_PREFIXES = (
    "Role: ",
    "Dates: ",
    "Project: ",
    "Work: ",
    "Technologies: ",
    "Highlights: ",
    "Title: ",
    "Degree: ",
    "Institution: ",
    "Skill: ",
    "Group: ",
    "Proficiency: ",
    "Subtitle: ",
    "GitHub: ",
    "Live: ",
    "Coursework: ",
    "Achievements: ",
)


def _tokens(text: str) -> list[str]:
    found = re.findall(r"[a-z0-9][a-z0-9+.#-]{1,}", text.lower())
    return [token for token in found if token not in STOP]


def _overlap(query_tokens: list[str], title: str, content: str) -> float:
    if not query_tokens:
        return 0.0
    title_low = title.lower()
    body_low = content.lower()
    score = 0.0
    for token in query_tokens:
        title_hits = title_low.count(token)
        body_hits = body_low.count(token)
        score += title_hits * 2.4
        score += min(body_hits, 6) * 1.0
    if "experience" in query_tokens and "experience" in body_low[:80]:
        score += 0.6
    return score / len(query_tokens)


def lexical_search(
    query: str,
    categories: list[str] | None = None,
    k: int = 8,
) -> list[dict]:
    sql = """
      SELECT title, category::text, content, source_table, source_id
      FROM embeddings
    """
    params: list = []
    if categories:
        sql += " WHERE category::text = ANY(%s)"
        params.append(categories)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            fetched = cur.fetchall()

    query_tokens = _tokens(query)
    scored = []
    for title, category, content, source_table, source_id in fetched:
        score = _overlap(query_tokens, title, content)
        if score <= 0:
            continue
        scored.append(
            {
                "title": title,
                "category": category,
                "content": content,
                "source_table": source_table,
                "source_id": str(source_id),
                "score": score,
            }
        )
    scored.sort(key=lambda row: (-row["score"], row["title"]))
    return scored[:k]


def _clean_line(line: str) -> str:
    text = line.strip()
    for prefix in _PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
            break
    text = re.sub(r"\s*\(https?://[^)]+\)", "", text)
    return text.strip(" -")


def _spoken(text: str) -> str:
    for pattern, repl in _PERSON:
        text = re.sub(pattern, repl, text)
    for pattern, repl in _SPEAK:
        text = re.sub(pattern, repl, text)
    return re.sub(r"\bI is\b", "I am", text).strip()


def _line_score(query_tokens: list[str], line: str) -> float:
    low = line.lower()
    if low.startswith("category:") or low.startswith("github:") or low.startswith("live:"):
        return -1
    score = 0.0
    for token in query_tokens:
        score += low.count(token)
    # Prefer the record body over a short "Title:" label when both mention the topic.
    score += min(len(line), 500) / 5000
    if low.startswith("title:") or low.startswith("degree:") or low.startswith("skill:"):
        score *= 0.45
    if low.startswith("technologies:") or low.startswith("highlights:"):
        score *= 0.25
    if low.startswith("proficiency:") or low.startswith("group:"):
        score *= 0.2
    return score


def _prose_for(question: str, row: dict) -> str:
    lines = [line.strip() for line in row["content"].splitlines() if line.strip()]
    lines = [line for line in lines if not line.lower().startswith("category:")]
    if not lines:
        return ""
    query_tokens = _tokens(question) or _tokens(row["title"])
    best = max(lines, key=lambda line: _line_score(query_tokens, line))
    if _line_score(query_tokens, best) < 0:
        best = lines[0]
    role = next((line for line in lines if line.lower().startswith("role:")), "")
    dates = next((line for line in lines if line.lower().startswith("dates:")), "")
    body = _clean_line(best)
    if not body:
        return ""
    if role and best != role:
        lead = _clean_line(role)
        when = _clean_line(dates)
        if lead and when:
            body = f"{lead}, {when}. {body}"
        elif lead:
            body = f"{lead}. {body}"
    return _spoken(body)


def mock_answer(question: str, rows: list[dict]) -> str:
    if not rows:
        return (
            "I don’t have that on record yet. "
            "Email hassan87691@gmail.com or see the contact section on my portfolio."
        )
    paragraphs: list[str] = []
    for index, row in enumerate(rows[:3]):
        if index > 0:
            if row["category"] == "skill" and paragraphs:
                continue
            if row["score"] < rows[0]["score"] * 0.72:
                continue
        prose = _prose_for(question, row)
        if prose and prose not in paragraphs:
            paragraphs.append(prose)
        if len(paragraphs) == 2:
            break
    if not paragraphs:
        return (
            "I don’t have that on record yet. "
            "Email hassan87691@gmail.com or see the contact section on my portfolio."
        )
    text = "\n\n".join(paragraphs)
    if "hassan87691@gmail.com" not in text:
        text += "\n\nIf you want to talk through a role, email me at hassan87691@gmail.com."
    return text


def mock_match(rows: list[dict]) -> str:
    if not rows:
        return (
            "## Not on record\n\n"
            "Nothing in the portfolio records overlapped that description.\n\n"
            "## CTA\n\nEmail hassan87691@gmail.com."
        )
    lines = "\n".join(f"- {row['title']}" for row in rows[:5])
    return (
        "## Strong overlap\n\n"
        f"{lines}\n\n"
        "## Evidence\n\n"
        "These are the closest stored records. Skills that do not appear there are not claimed.\n\n"
        "## CTA\n\nEmail hassan87691@gmail.com."
    )
