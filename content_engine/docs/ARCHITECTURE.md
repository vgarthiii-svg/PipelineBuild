# Architecture — Content Creator Engine

This document describes the system as implemented: a self-contained full-stack
app (zero-build vanilla-JS SPA + FastAPI + SQLAlchemy) organized around a modular
**AI provider** abstraction and a pluggable **engines** layer, runnable with one
command and **with or without** an AI key.

---

## 1. High-Level Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Browser — Vanilla-JS SPA  (frontend/)                                     │
│  index.html · js/api.js (fetch wrapper) · js/app.js (hash router + views)  │
│  Views: Dashboard · New (wizard) · Project workspace · Library · Brands ·  │
│         Calendar · Style Guide · Settings                                  │
└───────────────┬───────────────────────────────────────────────────────────┘
                │  HTTP/JSON  (served same-origin from "/", static at /static)
                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  FastAPI app  (backend/app/main.py)                                        │
│  CORS · lifespan(init_db + seed) · GET /api/health · mounts SPA            │
│  Routers: meta · brands · projects · drafts · library · calendar · settings│
│  Deps (deps.py): get_current_user (auth seam) · provider() (AI access)     │
└───────┬───────────────────────────────┬───────────────────────────────────┘
        │                               │
        ▼                               ▼
┌─────────────────────────┐   ┌───────────────────────────────────────────┐
│  Engines (engines/)     │   │  AI layer (ai/)                           │
│  research · generation  │──▶│  provider.py: AIProvider interface        │
│  scoring · ap_style     │   │   ├─ AnthropicProvider (live)             │
│  platform_rules · repu… │   │   └─ MockProvider (deterministic fallback)│
│  export                 │   │  prompts.py: composable prompt modules    │
└───────────┬─────────────┘   └───────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Data layer (database.py + models.py) — SQLAlchemy 2.0                     │
│  SQLite (default)  ──set DATABASE_URL──▶  PostgreSQL / Supabase            │
│  users · brand_profiles · content_projects · research_briefs/sources ·    │
│  content_drafts · scores · revision_history · platform_rules ·            │
│  style_guide_rules · content_calendar · export_history · tags · …         │
└──────────────────────────────────────────────────────────────────────────┘

        Future export/publish seams: Google Drive · Gmail · Mailchimp ·
                                      HubSpot · WordPress
```

**Layering rule:** routers orchestrate; engines hold domain logic; engines depend
only on the `AIProvider` *interface*, never a vendor SDK; everything is configured
from the environment via `config.py`.

---

## 2. Request Lifecycle

A representative call — **generate a draft** (`POST /api/projects/{id}/generate`):

1. **SPA** (`api.js`) sends JSON over `fetch`. In single-user mode no auth header
   is required; an `X-User-Email` header is supported for the multi-user path.
2. **FastAPI** routes to `routers/projects.py:generate`.
3. **Dependencies resolve**: `get_db` yields a scoped `Session`;
   `get_current_user` resolves/auto-provisions the user; `provider()` returns the
   active `AIProvider`.
4. **Ownership check** (`_get_owned`) ensures the project belongs to the user.
5. **Context assembly**: the router loads the brand profile, the platform rule
   (DB exact match → DB by content-type → in-code `find_rule` fallback), and the
   latest research brief, and converts them to plain dicts.
6. **Engine call**: `generation.generate_draft(...)` builds a composed prompt via
   `prompts.build_generation_prompt(...)` and calls `provider.complete_json(...)`.
7. **Provider**: `AnthropicProvider` (live) or `MockProvider` (deterministic).
   The base `complete_json` defensively extracts a single JSON object; engines
   normalize/guarantee every field and degrade gracefully on parse failure.
8. **Persistence**: a new versioned `ContentDraft` row is written; project status
   advances (e.g. `idea/researching → drafted`); the session commits.
9. **Response**: the ORM row is serialized via a Pydantic `*_Out` schema and
   returned; the SPA re-renders the workspace.

Startup lifecycle (`main.py` `lifespan`): `init_db()` creates all tables
(idempotent `create_all`), then `seed_all()` inserts system platform rules and
system style-guide rules if missing.

---

## 3. Modular AI Provider Abstraction

File: `backend/app/ai/provider.py`. The rest of the app depends only on the
`AIProvider` interface, so vendors swap via the `AI_PROVIDER` env var.

```python
class AIProvider:
    name = "base"
    def complete(self, system, prompt, max_tokens=2000, temperature=0.7) -> str: ...
    def complete_json(self, system, prompt, max_tokens=3000) -> dict: ...
        # base impl appends "respond with a single JSON object" and extracts it
```

- **AnthropicProvider** — lazily imports the `anthropic` SDK (so the app loads
  without it configured), calls `messages.create` with the configured model
  (`ANTHROPIC_MODEL`, default `claude-opus-4-8`), and concatenates text blocks.
- **MockProvider** — dependency-free and **deterministic**. `complete_json`
  branches on lightweight markers in the prompt (scorecard / research brief /
  repurpose / draft) to return structured, on-spec output so the entire workflow
  (generate → score → revise → repurpose) works offline and in tests.

**Selection** (`get_ai_provider`): returns `AnthropicProvider` only when
`settings.ai_enabled` (provider is `anthropic` **and** a key is present), and
**falls back to `MockProvider` on any construction error** — the app is never
un-runnable. `get_research_provider` reuses the chat provider; the research engine
handles web-grounding semantics and labels synthesized output.

### Adding a new provider
1. Subclass `AIProvider`, set a unique `name`, implement `complete` (and override
   `complete_json` if the vendor has a native JSON/structured mode).
2. Lazily import the SDK inside `__init__` to keep startup dependency-light.
3. Wire it into `get_ai_provider()` keyed off a new `AI_PROVIDER` value (and add
   any `*_API_KEY` / model settings to `config.py`).
4. No engine, router, or prompt change is required — they depend on the interface.

---

## 4. Engines Layer

`backend/app/engines/` — each engine is pure domain logic that takes an
`AIProvider` plus plain dicts and returns plain dicts.

| Engine | Responsibility |
|--------|----------------|
| `platform_rules.py` | `CONTENT_TYPES`, `PLATFORMS`, `PLATFORM_RULE_SEED` (rules-as-data: structure/best-practices/constraints) and `find_rule` lookup. |
| `research.py` | Build research prompt → JSON brief; normalize all list fields; guarantee at least one source; stamp `model_used` + `generated_at`. |
| `generation.py` | `generate_draft` (structured draft, degrades to plain completion on parse error) and `revise_draft` (named editor actions). |
| `scoring.py` | `SCORE_CATEGORIES` (14 weighted) + `score_draft`: AI categories merged with the deterministic AP checker; weighted overall; full normalization/fallbacks. |
| `ap_style.py` | Rule-based AP/journalistic checker + custom rule merge; returns findings and a 0–100 `ap_score`. |
| `repurpose.py` | One source → many target formats; per-target completion fallback. |
| `export.py` | Markdown / HTML / text / CSV exporters + DOCX bytes (python-docx with text fallback). |

**Resilience pattern (everywhere):** call the provider, defensively parse,
normalize to a complete shape, and fall back to deterministic defaults — so a
malformed or absent model response never breaks the workflow.

---

## 5. Prompt Module System

File: `backend/app/ai/prompts.py`. Prompts are **composed from small modules**,
each grounding output in one slice of the user's inputs:

```
build_generation_prompt = brand_module + platform_module + audience_module
                        + research_module + AP_STYLE_MODULE + seo_module
                        + cta_module + compliance_module + task spec (JSON schema)
```

- **System prompts**: `SYSTEM_GENERATOR` (strategist + journalist + copywriter),
  `SYSTEM_SCORER` (rigorous, hype-penalizing editor), `SYSTEM_RESEARCHER`
  (pattern-synthesizing, source-citing researcher).
- **Context modules**: `brand_module`, `platform_module`, `audience_module`,
  `research_module`, `AP_STYLE_MODULE`, `seo_module`, `cta_module`,
  `compliance_module` — each emitted only when relevant and merged in order.
- **Task builders**: `build_generation_prompt`, `build_research_prompt`,
  `build_scoring_prompt` (injects the exact category keys + deterministic AP
  findings), `build_revision_prompt` (action→directive map), `build_repurpose_prompt`.

This guarantees output is **always tied to the inputs** (brand, platform,
audience, research, SEO, CTA, compliance) rather than generic — and that the same
inputs map deterministically to the MockProvider's structured stubs.

---

## 6. Auth Seam

File: `backend/app/deps.py`.

```python
def get_current_user(db, x_user_email: str | None = Header(None)) -> User:
    email = x_user_email or (default_user_email if single_user_mode else None)
    # single-user: auto-provision a default user; multi-user: require known user
```

- **Default (single-user dev mode):** `SINGLE_USER_MODE=1` auto-provisions
  `DEFAULT_USER_EMAIL` and uses it for every request — zero auth friction.
- **Multi-user path:** set `SINGLE_USER_MODE=0`; requests then require a resolvable
  user (an `X-User-Email` header in the current implementation).
- **Production auth (Clerk / Supabase / Auth0):** replace **only**
  `get_current_user` to resolve the user from a verified JWT. Every router already
  depends on this single function and scopes all queries by `user.id`, so the rest
  of the app is unchanged.

---

## 7. Data Layer

Files: `backend/app/database.py`, `models.py`.

- **SQLAlchemy 2.0**, declarative `Base`, `SessionLocal` factory, `get_db`
  dependency, and idempotent `init_db()`.
- **SQLite by default** (`sqlite:///./data/content_engine.db`); the data directory
  is auto-created and `check_same_thread=False` is set for the SQLite case.
- **Postgres/Supabase:** set `DATABASE_URL` (e.g.
  `postgresql+psycopg://user:pass@host:5432/db`). `pool_pre_ping=True` is on; no
  model changes needed. **JSON columns** use SQLAlchemy's portable `JSON` type so
  list/dict fields work on both backends.

**Tables (models.py):** `users`, `brand_profiles`, `content_projects`,
`research_briefs`, `research_sources`, `content_drafts`, `scores`,
`revision_history`, `platform_rules`, `style_guide_rules`, `content_calendar`,
`export_history`, `tags` (+ `content_tags` M2M), `saved_snippets`, `app_settings`.
Ownership cascades from `users`; drafts version per project; scores/revisions/
sources cascade from their parents.

---

## 8. Key Engineering Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **FastAPI + SQLAlchemy + SQLite (Postgres-ready)** instead of Next.js + Supabase | Runs in any environment with **one command** and no external service provisioning; swap to managed Postgres later by setting `DATABASE_URL` — no rewrite. |
| 2 | **Modular AI provider with a deterministic mock fallback** | The app is **always runnable, testable, and demoable** with zero keys; real keys unlock live quality. Engines never depend on a vendor SDK. |
| 3 | **Pluggable research provider** | Uses model knowledge / web tooling when a key is present, else a clearly-labeled *synthesized* brief — the research step never blocks the workflow and never misrepresents sourcing. |
| 4 | **Auth seam isolated to one dependency** | Single-user dev mode by default; a drop-in path to Clerk/Supabase/Auth0 by replacing `deps.get_current_user`, because every route already scopes by the resolved user. |

Supporting decision: **rules-as-data** (platform rules + style-guide rules live in
the DB, seeded from code) so best practices and editorial rules are editable in
Settings without code changes, and the AP-style category score is **deterministic
and auditable**.

---

## 9. Integration Seams (future export/publish targets)

The provider/engine boundaries are built so external services attach as
**export/publish targets without touching core logic**:

| Target | Seam | Intended use |
|--------|------|--------------|
| **Google Drive** | new format in `engines/export.py` + an export route | push drafts/exports to Drive |
| **Gmail** | export/publish action on a draft | create email drafts from `email` content |
| **Mailchimp** | publish target for `email`/`newsletter` | push campaigns + subject A/B variants |
| **HubSpot** | publish/CRM target | sync content, campaigns, and assets |
| **WordPress** | publish target for `blog`/`website` | publish posts/pages with SEO metadata |

Pattern: add a destination behind the existing export/publish surface (mirroring
`EXPORTERS` and `export_history`), keep credentials in `config.py`, and reuse the
already-structured draft payload (title, body, headlines, CTAs, SEO fields). No
engine or prompt changes are required.

---

## 10. How the Frontend Is Served

- The SPA is **zero-build vanilla JS** (`frontend/index.html`, `js/api.js`,
  `js/app.js`, `css/styles.css`) — no bundler, no framework.
- FastAPI (`main.py`) computes `FRONTEND_DIR` (`../../frontend`), **mounts it at
  `/static`** via `StaticFiles`, and serves `index.html` at `GET /`. The app is
  therefore **same-origin** with the API (CORS is also open as a convenience).
- `api.js` is a thin `fetch` wrapper that targets relative `/api/...` paths and
  surfaces `detail` messages on errors; `app.js` is a hash-based router rendering
  views (Dashboard, New wizard, Project workspace, Library, Brands, Calendar,
  Style Guide, Settings) and reads dropdown option sets once from `/api/meta`.
- **Run it:** `bash run.sh` (installs deps, creates `.env` from the example in
  mock mode if missing, then `uvicorn app.main:app` on port 8000). App at
  `http://localhost:8000`, interactive API docs at `/docs`.
