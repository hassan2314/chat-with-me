import json
from pathlib import Path

from psycopg.types.json import Json

from app.compose import (
    about_text,
    education_text,
    experience_text,
    project_text,
    skill_text,
)
from app.db import get_conn
from app.rag import EMBED_DIM, embed, upsert_embedding
from app.settings import llm_mode

SEED_PATH = Path(__file__).resolve().parents[1] / "seed" / "portfolio.json"


def wipe() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                TRUNCATE
                  embeddings,
                  experience_projects,
                  experience,
                  projects,
                  skills,
                  education,
                  about,
                  chat_logs
                RESTART IDENTITY CASCADE
                """
            )
        conn.commit()


def _embed_row(category: str, table: str, source_id, title: str, content: str) -> None:
    if llm_mode() == "mock":
        vector = [0.0] * EMBED_DIM
    else:
        vector = embed([content], task_type="RETRIEVAL_DOCUMENT")[0]
    upsert_embedding(category, table, str(source_id), title, content, vector)


def load_seed(path: Path = SEED_PATH) -> dict:
    data = json.loads(path.read_text())
    counts = {"about": 0, "education": 0, "experience": 0, "skill": 0, "project": 0}
    pending: list[tuple] = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            for row in data.get("about", []):
                cur.execute(
                    """
                    INSERT INTO about (slug, title, body, extra)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        row["slug"],
                        row["title"],
                        row["body"],
                        Json(row.get("extra") or {}),
                    ),
                )
                source_id = cur.fetchone()[0]
                pending.append(
                    ("about", "about", source_id, row["title"], about_text(row))
                )
                counts["about"] += 1

            for row in data.get("education", []):
                cur.execute(
                    """
                    INSERT INTO education
                      (degree, institution, start_year, end_year,
                       description, coursework, achievements)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        row["degree"],
                        row["institution"],
                        row.get("start_year"),
                        row.get("end_year"),
                        row.get("description"),
                        row.get("coursework") or [],
                        row.get("achievements") or [],
                    ),
                )
                source_id = cur.fetchone()[0]
                title = f"{row['degree']} · {row['institution']}"
                pending.append(
                    ("education", "education", source_id, title, education_text(row))
                )
                counts["education"] += 1

            for row in data.get("experience", []):
                cur.execute(
                    """
                    INSERT INTO experience
                      (title, company, location, start_label, end_label,
                       highlights, technologies)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        row["title"],
                        row["company"],
                        row.get("location"),
                        row.get("start_label"),
                        row.get("end_label"),
                        row.get("highlights") or [],
                        row.get("technologies") or [],
                    ),
                )
                exp_id = cur.fetchone()[0]
                projects = row.get("projects") or []
                for project in projects:
                    cur.execute(
                        """
                        INSERT INTO experience_projects
                          (experience_id, name, url, bullets)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            exp_id,
                            project.get("name"),
                            project.get("url"),
                            project.get("bullets") or [],
                        ),
                    )
                title = f"{row['title']} · {row['company']}"
                pending.append(
                    (
                        "experience",
                        "experience",
                        exp_id,
                        title,
                        experience_text(row, projects),
                    )
                )
                counts["experience"] += 1

            for row in data.get("skills", []):
                cur.execute(
                    """
                    INSERT INTO skills (group_name, name, level)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (row["group_name"], row["name"], row.get("level")),
                )
                source_id = cur.fetchone()[0]
                title = f"{row['name']} · {row['group_name']}"
                pending.append(
                    ("skill", "skills", source_id, title, skill_text(row))
                )
                counts["skill"] += 1

            for row in data.get("projects", []):
                cur.execute(
                    """
                    INSERT INTO projects
                      (title, subtitle, description, technologies,
                       github_url, live_url, featured)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        row["title"],
                        row.get("subtitle"),
                        row["description"],
                        row.get("technologies") or [],
                        row.get("github_url"),
                        row.get("live_url"),
                        bool(row.get("featured")),
                    ),
                )
                source_id = cur.fetchone()[0]
                pending.append(
                    ("project", "projects", source_id, row["title"], project_text(row))
                )
                counts["project"] += 1

        conn.commit()

    for item in pending:
        _embed_row(*item)

    return counts


def run_seed() -> dict:
    if not SEED_PATH.is_file():
        raise FileNotFoundError(f"missing seed file: {SEED_PATH}")
    wipe()
    counts = load_seed()
    return {"status": "ok", "counts": counts}


if __name__ == "__main__":
    result = run_seed()
    print(result)
