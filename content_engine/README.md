# Content Creator Engine

A production-ready **marketing command center** — not a basic AI writing tool.
Select a platform and content type, feed in your business context, run live
research on what's working, then **generate → score → revise → repurpose →
organize** high-quality content that follows platform best practices, AP-style
journalistic principles, brand voice, SEO rules, and conversion strategy.

> Built as a self-contained full-stack app that runs with **one command** and
> works **with or without** an AI key (a deterministic mock provider keeps the
> whole workflow demoable offline).

---

## ✨ What it does

- **13 content types** — LinkedIn posts, email campaigns, website & landing-page
  copy, blog posts, newsletters, social posts, ad copy, thought leadership,
  sales enablement, press-style announcements, SEO briefs, and repurposing.
- **Research engine** — timestamped, source-cited research briefs: trends,
  high-performing patterns, competitor themes, hooks, SEO keywords, search
  intent, related questions, audience pain points, content gaps, and risks.
  It synthesizes *patterns*, never copies viral content.
- **Platform best-practices engine** — data-driven structure + rules per
  platform/content-type (editable in Settings).
- **AP-style layer** — a practical, rule-based journalistic checker (no
  copyrighted stylebook text) plus user-definable custom editorial rules.
- **14-category scoring engine** — every draft scored 1–100 with what's
  working, what's weak, and concrete improvements. AP-style score is auditable
  (driven by the deterministic checker).
- **Draft editor** — rewrite, shorten, expand, make professional/conversational/
  direct, add stats, strengthen CTA, remove fluff, convert to AP style, generate
  variations — plus headline/CTA/hook options.
- **Repurposing engine** — turn one piece into many formats.
- **Content library + calendar** — search, filter, tag, schedule, and track
  status (idea → researching → drafted → needs review → approved → scheduled →
  published → archived).
- **Brand profiles** — reusable voice, words to use/avoid, competitors, proof
  points, offers, compliance rules, boilerplate, and more.
- **Exports** — Markdown, HTML, plain text, CSV, DOCX (PDF via HTML print).

---

## 🚀 Quick start

```bash
cd content_engine
bash run.sh
# open http://localhost:8000   (API docs at /docs)
```

That's it. The app starts in **mock mode** (no key needed) so you can click
through the entire workflow immediately. To enable live AI + research:

```bash
# content_engine/backend/.env
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
RESEARCH_PROVIDER=anthropic_web
```

### Run the tests

```bash
cd content_engine/backend
AI_PROVIDER=mock python -m pytest tests/ -q     # 10 tests, end-to-end
```

---

## 🧱 Architecture (at a glance)

```
content_engine/
├── backend/                 FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── config.py        env-driven settings (providers, DB, auth)
│   │   ├── database.py      SQLite (default) / Postgres-ready engine
│   │   ├── models.py        13+ tables (the durable data structure)
│   │   ├── schemas.py       Pydantic request/response models
│   │   ├── deps.py          auth seam + provider access
│   │   ├── seed.py          seeds platform & style rules
│   │   ├── ai/
│   │   │   ├── provider.py   modular AI providers (Anthropic + Mock)
│   │   │   └── prompts.py    modular prompt template system
│   │   ├── engines/
│   │   │   ├── platform_rules.py  best-practices rules engine
│   │   │   ├── ap_style.py        AP-style checker
│   │   │   ├── research.py        research engine
│   │   │   ├── generation.py      draft generation + revision
│   │   │   ├── scoring.py         14-category scoring
│   │   │   ├── repurpose.py       repurposing engine
│   │   │   └── export.py          multi-format export
│   │   ├── routers/         meta, brands, projects, drafts, library,
│   │   │                    calendar, settings
│   │   └── main.py          app wiring + serves the SPA
│   └── tests/               engine + API tests
├── frontend/                zero-build vanilla-JS SPA
│   ├── index.html
│   ├── css/styles.css
│   └── js/{api.js, app.js}
└── docs/                    PRD, architecture, schema, wireframes, API,
                             prompts, research workflow, scoring, testing,
                             deployment
```

**Key engineering decisions** (full rationale in `docs/ARCHITECTURE.md`):

1. **FastAPI + SQLAlchemy + SQLite (Postgres-ready)** instead of Next.js +
   Supabase — so the app runs in any environment with one command and no
   external service provisioning. Swap to Postgres by setting `DATABASE_URL`.
2. **Modular AI provider** with a deterministic **mock fallback** — the app is
   always runnable, testable, and demoable; real keys unlock live quality.
3. **Pluggable research provider** — uses model knowledge / web tooling when a
   key is present, else a clearly-labeled synthesized brief.
4. **Auth seam** — single-user dev mode by default; drop-in path to
   Clerk/Supabase/Auth0 by replacing one dependency (`deps.get_current_user`).

---

## 📚 Documentation

| Doc | Contents |
|-----|----------|
| `docs/PRD.md` | Product requirements |
| `docs/ARCHITECTURE.md` | System & component architecture + decisions |
| `docs/DATABASE_SCHEMA.md` | Tables, columns, relationships |
| `docs/WIREFRAMES.md` | Screen-by-screen UI plan |
| `docs/API_ROUTES.md` | Every endpoint, request/response |
| `docs/PROMPT_TEMPLATES.md` | The modular prompt system |
| `docs/RESEARCH_WORKFLOW.md` | How research is gathered & cited |
| `docs/SCORING_LOGIC.md` | The 14 categories & weighting |
| `docs/TESTING_PLAN.md` | Test strategy & coverage |
| `docs/DEPLOYMENT.md` | Local, Docker, and cloud deployment |

---

## 🔌 Integrations (roadmap)

The provider/engine seams are built so Google Drive, Gmail, Mailchimp, HubSpot,
WordPress, and scheduling tools can be added as export/publish targets without
touching core logic. See `docs/ARCHITECTURE.md` → *Integration seams*.
