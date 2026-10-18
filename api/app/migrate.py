"""Idempotent schema so Neon / first Cloud boot does not depend on Docker init."""

from app.db import get_conn

STATEMENTS = (
    # Supabase installs pgvector in the `extensions` schema.
    "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions",
    """
    DO $$ BEGIN
      CREATE TYPE record_category AS ENUM
        ('about', 'education', 'experience', 'skill', 'project');
    EXCEPTION
      WHEN duplicate_object THEN NULL;
    END $$
    """,
    """
    CREATE TABLE IF NOT EXISTS about (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      slug text UNIQUE NOT NULL,
      title text NOT NULL,
      body text NOT NULL,
      extra jsonb NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS education (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      degree text NOT NULL,
      institution text NOT NULL,
      start_year int,
      end_year int,
      description text,
      coursework text[] NOT NULL DEFAULT '{}',
      achievements text[] NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS experience (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      title text NOT NULL,
      company text NOT NULL,
      location text,
      start_label text,
      end_label text,
      highlights text[] NOT NULL DEFAULT '{}',
      technologies text[] NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS experience_projects (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      experience_id uuid NOT NULL REFERENCES experience(id) ON DELETE CASCADE,
      name text,
      url text,
      bullets text[] NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS skills (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      group_name text NOT NULL,
      name text NOT NULL,
      level int
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS projects (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      title text NOT NULL,
      subtitle text,
      description text NOT NULL,
      technologies text[] NOT NULL DEFAULT '{}',
      github_url text,
      live_url text,
      featured boolean NOT NULL DEFAULT false
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS embeddings (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      category record_category NOT NULL,
      source_table text NOT NULL,
      source_id uuid NOT NULL,
      title text NOT NULL,
      content text NOT NULL,
      embedding vector(768) NOT NULL,
      UNIQUE (source_table, source_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS embeddings_hnsw
      ON embeddings USING hnsw (embedding vector_cosine_ops)
    """,
    """
    CREATE INDEX IF NOT EXISTS embeddings_category_idx
      ON embeddings (category)
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_logs (
      id bigserial PRIMARY KEY,
      question text NOT NULL,
      categories text[] NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
)


def apply_schema() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            for statement in STATEMENTS:
                cur.execute(statement)
        conn.commit()
