# Deployment

## Local (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional; demo works with no keys
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
cd frontend && npm install && npm run dev   # http://localhost:5173
python scripts/demo_review.py              # CLI demo review
```

## Docker Compose (full stack)

```bash
docker compose up --build
# api: http://localhost:8000  ·  frontend: http://localhost:5173
# postgres (pgvector) + redis + celery worker included
```

Services: `postgres` (pgvector/pgvector:pg16, healthchecked), `redis`,
`api`, `worker` (Celery; falls back to in-process queue without a broker),
`frontend` (nginx serving the Vite build). Volumes: `pgdata` persists the DB.
Set `CODESENTRY_JWT_SECRET` and `GITHUB_WEBHOOK_SECRET` in the environment —
never commit them.

> Note: Docker is **not installed in the build environment** used to create
> this repo, so `docker compose up` was not executed here. The compose file
> was validated for YAML syntax; run it on a Docker host before claiming a
> containerised deployment works.

## Render (backend) + Vercel (frontend)

- Render: use `render.yaml` (Python 3.12.0 pinned — Render's default 3.14
  breaks pydantic-core). Set `DATABASE_URL` (Postgres), `REDIS_URL`,
  `CODESENTRY_JWT_SECRET`, `GITHUB_WEBHOOK_SECRET`, `GROQ_API_KEY` (optional)
  in the Render dashboard. Health check path: `/health`.
- Vercel: import the repo, set root to `frontend` (or use the included
  `vercel.json`), set `VITE_API_URL` to the Render backend URL, deploy.

## Production checklist

- [ ] `CODESENTRY_JWT_SECRET` is a long random value (the dev default is insecure).
- [ ] `GITHUB_WEBHOOK_SECRET` set; webhooks rejected without a valid signature.
- [ ] Postgres `DATABASE_URL` set (SQLite is for local dev only).
- [ ] `GROQ_API_KEY` set only if hosted LLM review is wanted; otherwise the
      deterministic engine runs (findings still real, just rule-based).
- [ ] Alembic migrations applied: `alembic upgrade head`.
- [ ] `docker compose up` verified on the target host.
