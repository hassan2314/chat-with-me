# Portfolio Chat API

Recruiter-facing chatbot for [hassanahmed.dev](https://genuine-kleicha-d80d7d.netlify.app/).
Answers come from Postgres (experience, projects, skills, education, about), not from the static site.

```text
Portfolio widget (later)
        │
        ▼
   FastAPI
   POST /v1/chat          → classify → search → answer
   POST /v1/chat/stream   → same, SSE tokens
   POST /v1/match-jd      → compare a job post to my stack
   GET  /v1/suggestions
   GET  /health
        │
        ▼
   PostgreSQL + pgvector
   one embedding per record, tagged with a category
```

## Setup

Needs Python 3.12, Docker, and a [Gemini API key](https://aistudio.google.com/apikey).

```fish
cp .env.example .env
# put GEMINI_API_KEY in .env

docker compose up -d

cd api
python3.12 -m venv .venv
source .venv/bin/activate.fish
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload
```

API: http://127.0.0.1:8000
Swagger: http://127.0.0.1:8000/docs

Postgres is on **5433** so it does not clash with other local DBs.

## Endpoints

| Method | Path | What it does |
|--------|------|----------------|
| GET | `/health` | API + `SELECT 1` |
| POST | `/v1/chat` | Full JSON answer + citations |
| POST | `/v1/chat/stream` | SSE: `meta` → `token` → `done` |
| POST | `/v1/match-jd` | `{ "job_description": "..." }` |
| GET | `/v1/suggestions` | Starter questions |
| POST | `/v1/seed` | Reload `api/seed/portfolio.json` (`X-Admin-Secret`) |

```fish
curl http://127.0.0.1:8000/health

curl http://127.0.0.1:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Why should we hire you?"}'

curl -N http://127.0.0.1:8000/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"question":"what is your experience with NestJS?"}'
```

After you edit `api/seed/portfolio.json`:

```fish
cd api
python -m app.seed
```

## Deploy (FastAPI Cloud)

Deploy from the **repo root** (Cloud looks for `main.py` there). `main.py` loads the real app from `api/`.

Cloud does **not** run your local Docker Postgres. Use [Supabase](https://supabase.com/dashboard) (or [Neon](https://fastapicloud.com/docs/integrations/neon-integration/)) with the **pgvector** extension. On boot the API creates tables if they are missing.

This repo’s Supabase project: **chat-with-me** (`jzzvivgngfyivzwrdaub`, `ap-south-1`). Schema + pgvector are already applied. Copy the DB URL from [Database settings](https://supabase.com/dashboard/project/jzzvivgngfyivzwrdaub/settings/database) (use the URI with `sslmode=require`).

```fish
cd /home/hassan/Documents/dev/chat-with-me
fastapi login
# or: uv run fastapi login

# Point Cloud at Supabase (URI from dashboard; keep sslmode=require)
fastapi cloud env set --secret DATABASE_URL "postgresql://postgres....?sslmode=require"
fastapi cloud env set --secret GEMINI_API_KEY "your_key"
fastapi cloud env set --secret GOOGLE_API_KEY "your_key"
fastapi cloud env set --secret ADMIN_SECRET "a-long-random-string"
fastapi cloud env set PORTFOLIO_URL "https://genuine-kleicha-d80d7d.netlify.app"
fastapi cloud env set CHAT_MODEL "gemini-3.6-flash"
fastapi cloud env set CORS_ORIGINS "https://genuine-kleicha-d80d7d.netlify.app"

fastapi deploy
```

Seed **once** against the cloud database (45 Gemini embeds). Prefer local so the request does not time out:

```fish
cd api
source .venv/bin/activate.fish
# temporarily point DATABASE_URL in ../.env at the Supabase URL (sslmode=require)
python -m app.seed
```

Or after deploy:

```fish
curl -X POST https://YOUR-APP.fastapicloud.dev/v1/seed \
  -H "X-Admin-Secret: your-admin-secret"
```

Check:

```fish
curl https://YOUR-APP.fastapicloud.dev/health
```

`db` should be `ok`. Then try `/v1/chat`.

Do not commit `.env`. Keep `ADMIN_SECRET` long; `/v1/reset` wipes the database.

## Notes

- The website stays static. This API is the live source for chat.
- Do not commit `.env`.
- Default local port is `8000` (`PORT` in `.env`).
- FastAPI Cloud entrypoint is repo-root `main.py` (`main:app`).
