import os
import time
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.db import get_conn

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768

_client = None


def gemini() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def embed(
    texts: list[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    if not texts:
        return []

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = gemini().models.embed_content(
                model=EMBED_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=EMBED_DIM,
                ),
            )
            vectors = [list(item.values) for item in response.embeddings]
            for vec in vectors:
                if len(vec) != EMBED_DIM:
                    raise ValueError(f"expected {EMBED_DIM} dims, got {len(vec)}")
            return vectors
        except genai_errors.ServerError as exc:
            last_error = exc
            time.sleep(1.2 * (attempt + 1))
    raise last_error or RuntimeError("embed failed")


def as_vector(vec: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vec) + "]"


def upsert_embedding(
    category: str,
    source_table: str,
    source_id: str,
    title: str,
    content: str,
    vector: list[float],
) -> None:
    literal = as_vector(vector)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO embeddings
                  (category, source_table, source_id, title, content, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (source_table, source_id) DO UPDATE SET
                  category = EXCLUDED.category,
                  title = EXCLUDED.title,
                  content = EXCLUDED.content,
                  embedding = EXCLUDED.embedding
                """,
                (category, source_table, source_id, title, content, literal),
            )
        conn.commit()


def search(
    query: str,
    categories: list[str] | None = None,
    k: int = 8,
) -> list[dict[str, Any]]:
    qvec = embed([query], task_type="RETRIEVAL_QUERY")[0]
    literal = as_vector(qvec)
    sql = """
      SELECT title, category::text, content, source_table, source_id,
             1 - (embedding <=> %s::vector) AS score
      FROM embeddings
    """
    params: list[Any] = [literal]
    if categories:
        sql += " WHERE category::text = ANY(%s)"
        params.append(categories)
    sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
    params.extend([literal, k])

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        {
            "title": title,
            "category": category,
            "content": content,
            "source_table": source_table,
            "source_id": str(source_id),
            "score": float(score),
        }
        for title, category, content, source_table, source_id, score in rows
    ]
