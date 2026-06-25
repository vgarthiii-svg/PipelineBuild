# Deployment — Content Creator Engine

The backend (FastAPI) serves both the JSON API **and** the static frontend SPA,
so a single process is all you need to deploy. It defaults to SQLite and the
deterministic mock provider, so it boots with zero configuration and unlocks live
AI/research and Postgres purely through environment variables.

---

## (a) Local — `run.sh`

The fastest path. From the repo:

```bash
cd content_engine
bash run.sh
# App:      http://localhost:8000
# API docs: http://localhost:8000/docs
```

`run.sh` does three things (`content_engine/run.sh`):

1. `pip install -r requirements.txt` (falls back from `pip3` to `pip`).
2. Creates `backend/.env` from `.env.example` if missing (so it starts in **mock
   mode** until you add keys).
3. Starts `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.

To run it manually instead:

```bash
cd content_engine/backend
pip install -r requirements.txt
cp .env.example .env          # then edit as needed
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The app starts fully usable in mock mode — click through the entire workflow with
no key. Add an `ANTHROPIC_API_KEY` to enable live generation + research.

---

## (b) Environment variables (`backend/.env.example`)

Copy `.env.example` to `.env` and fill in. Everything has a working default.

| Variable | Default | Purpose |
|----------|---------|---------|
| `AI_PROVIDER` | `anthropic` | AI provider for generation/scoring/revision. `anthropic` \| `mock`. Falls back to mock behavior when no key is set. |
| `ANTHROPIC_API_KEY` | _(empty)_ | Anthropic key. **Empty = mock mode** (deterministic, offline). Set this to enable live AI. |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | Default model for generation/scoring/revision. |
| `RESEARCH_PROVIDER` | `anthropic_web` | Research provider. `anthropic_web` (live, key required) \| `mock` (clearly-labeled synthesized brief). |
| `DATABASE_URL` | `sqlite:///./data/content_engine.db` | SQLAlchemy URL. Set a `postgresql+psycopg://…` URL for Postgres/Supabase. |
| `APP_ENV` | `development` | Environment label; set to `production` in prod. |
| `SECRET_KEY` | `change-me-in-production` | App secret. **Must be replaced** with a strong random value in production. |
| `SINGLE_USER_MODE` | `1` | `1` auto-provisions a single user (no auth header). Set `0` to require authentication. |
| `DEFAULT_USER_EMAIL` | `owner@local` | The auto-provisioned user's email in single-user mode. |

To enable live AI + research:

```bash
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
RESEARCH_PROVIDER=anthropic_web
```

---

## (c) Docker (backend serves the frontend)

A single image runs the whole app. Place this `Dockerfile` at `content_engine/`.

```dockerfile
# Content Creator Engine — single-image deploy (API + SPA)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the application (backend) and the static frontend it serves
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Persist the SQLite database on a mounted volume
RUN mkdir -p /app/backend/data
VOLUME ["/app/backend/data"]

WORKDIR /app/backend
EXPOSE 8000

# Production server: uvicorn (add gunicorn workers for higher concurrency)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> Note: `app.main` serves `frontend/` as static assets. The Dockerfile copies the
> `frontend/` directory next to `backend/` (mirroring the repo layout) so those
> static routes resolve. Adjust the relative paths only if you change the repo
> structure.

Build and run:

```bash
cd content_engine
docker build -t content-engine .

# Mock mode (no key) with a persistent SQLite volume:
docker run -d --name content-engine -p 8000:8000 \
  -v content_engine_data:/app/backend/data \
  content-engine

# Live AI + research:
docker run -d --name content-engine -p 8000:8000 \
  -v content_engine_data:/app/backend/data \
  -e AI_PROVIDER=anthropic \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e RESEARCH_PROVIDER=anthropic_web \
  -e APP_ENV=production \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  content-engine
```

Then open `http://localhost:8000`. (Pass an `.env` with `--env-file .env` instead
of repeating `-e` flags if you prefer.)

---

## (d) PostgreSQL / Supabase

The data layer is SQLAlchemy-based and Postgres-ready — switching is a single
environment variable. No application code changes are required.

```bash
# Generic Postgres
DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/DBNAME

# Supabase (use the connection string from the project's Database settings)
DATABASE_URL=postgresql+psycopg://postgres:PASS@db.<project-ref>.supabase.co:5432/postgres
```

Notes:
- Add a Postgres driver to the image/environment (e.g. `psycopg[binary]`) since
  `requirements.txt` ships only the SQLite-capable default stack.
- Tables are created and platform/style rules are seeded by the app's lifespan
  handler on first boot, so a fresh empty Postgres database is sufficient.
- With managed Postgres you no longer need the SQLite volume — drop the
  `-v …/data` mount.

---

## (e) Production notes

- **Secrets** — set a strong `SECRET_KEY` (e.g. `openssl rand -hex 32`); never
  ship the placeholder. Inject keys via the platform's secret store, not the image.
- **Real authentication** — set `SINGLE_USER_MODE=0` and wire a real auth provider
  at the `deps.get_current_user` seam (Clerk/Supabase/Auth0). Single-user mode is
  for local/dev only and exposes all data with no auth.
- **ASGI / process model** — run without `--reload`. For higher concurrency use
  Gunicorn with the uvicorn worker class:

  ```bash
  gunicorn app.main:app \
    -k uvicorn.workers.UvicornWorker \
    -w 4 -b 0.0.0.0:8000 --timeout 120
  ```

  (Add `gunicorn` to requirements when using this.) Size workers to CPU; note
  long AI calls — keep a generous timeout.
- **Reverse proxy** — front the app with Nginx/Caddy/ALB for TLS termination,
  gzip, request limits, and static caching. Forward `X-Forwarded-*` headers.
- **Persistence** — with SQLite, mount a **persistent volume** at
  `/app/backend/data` (data is lost otherwise on container replacement). For
  multi-instance or zero-downtime deploys, prefer **managed Postgres** over
  SQLite (SQLite does not handle concurrent writers across replicas).
- **Provider config** — set `ANTHROPIC_API_KEY` (and `RESEARCH_PROVIDER=anthropic_web`)
  for live quality; leaving the key empty silently degrades to mock output, which
  is not what production users want. Optionally pin `ANTHROPIC_MODEL`.
- **Set `APP_ENV=production`** and run health checks against `GET /api/health`.
- **Backups / migrations** — back up the SQLite file or Postgres database
  regularly. The current schema is created on boot; adopt a migration tool
  (e.g. Alembic) before making breaking schema changes in production.
