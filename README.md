# BD Pipeline Agent

A local web application for managing business development pipelines across multiple clients. Turns prospect companies into ranked, scored, scheduled workstreams.

Built for a solo BD operator (Vinnie Garth, Vinsational Consulting) managing introductions between clients and prospect companies.

---

## What it does

Pick any company as your "lens". Every other company in the system is scored against that lens using a 4-layer model (identity filter → product-market fit → friction → intent) plus your relationship strength. The result: a ranked pipeline with Hot/Warm/Monitor/Pass tiers, one-click intro generation, and nightly automation that keeps the data fresh.

**Core ideas:**

- Every company in the pool can be both a **client** (lens) and a **prospect** (candidate). The same data works either direction.
- Scoring is **directional**. Erie scored against Tivly is different from Erie scored against Circle AI.
- All heuristic scoring is **free** — no API cost. Claude is used only for explicit Deep Research and Intro Generation, both gated behind user approval.
- Pipeline math is **visible**. Every score has a traceable breakdown you can inspect on hover.

---

## Quick start

```bash
# One-time setup
cp .env.example .env       # then add your API keys
pip3 install -r requirements.txt

# Run the server
bash run.sh                # → http://localhost:8000
```

Or on macOS, the LaunchAgent plist at `~/Library/LaunchAgents/com.vinsational.bd-pipeline-agent.plist` runs it automatically at login.

---

## The dashboard

Three main views in the top nav:

| View | Purpose |
|---|---|
| **Pipeline** | The ranked table of prospects for the currently-selected lens. Filters, search, tier summary, score breakdown on hover. |
| **Activity** | Chronological log of scoring events, tier changes, intros sent, etc. |
| **Agents** | Scheduled background jobs + the ad-hoc HubSpot import tool. |

### Three control layers above the pipeline table

- **Layer 1: Client** — the lens. Dropdown lists every company in the system; picking any one rescores the entire pipeline against that company's profile. Active clients (your real engagements) sort first with a ✓.
- **Layer 2: Data Sources** — toggles which external sources feed the Relationship Score (Gmail, HubSpot, Calendar, conference DB, etc.). Each source reports Active or Stub.
- **Layer 3: Scoring Weights** — how much PMF vs RS weighs in the final Matchmaker score. Presets (60/40, 80/20, 50/50, 30/70) or custom sliders.

Below those: the **Scoring Criteria panel** (20-criterion library in 4 groups, with quick-start presets) and the **Identity Filters panel** (hard gates with live preview).

### Pipeline table features

- Sticky header, sortable columns with direction indicators
- Inline search, tier filter chips (summary cards double as filters)
- Keyboard shortcuts: `/` to search, `j`/`k` to navigate rows, `Esc` to close panels
- Row density toggle (Comfortable / Compact) + column visibility menu, both persisted
- Score delta arrows (▲/▼) show how much each company moved since the last reload
- Click any row for the detail panel

### Detail panel (per company)

Seven tabs in workflow order: **Profile → Scoring → Contacts → Intent → Intro → Behavior → Activity**.

- **Scoring** tab embeds the full score breakdown (PMF criteria with ✓/◐/✗, RS, Friction, Intent, formula) plus manual override buttons per criterion.
- **Intro** tab has a target-contact picker, inline subject/body editing with autosave, a voice-rules checker that flags em dashes and banned words, and a copy-full-email button.
- Destructive actions (Remove, Delete Everywhere) are tucked behind a ⋯ overflow menu.

### Tooltips

Every column header, tier badge, criterion tile, criteria group, and layer tile has a hover tooltip explaining what it measures, why it matters, and how to use it.

---

## Scoring model

See [`docs/SCORING_ARCHITECTURE.md`](docs/SCORING_ARCHITECTURE.md) for the full diagram. Quick version:

```
4-LAYER PIPELINE
  1. Identity Filter  (hard gate: size, geo, vertical)  → pass / filtered
  2. PMF              (Σ criterion_scores × weights)    → 0-100
  3. Friction         (behavior profile overlap)         → 0.7-1.0 coefficient
  4. Intent           (active buying signals)            → 1.0-1.5 multiplier

MATCHMAKER SCORE = min(100, (PMF × Friction × Intent) + (RS/5 × 20))

TIERS
  80+   Hot       priority outreach
  60-79 Warm      secondary priority
  40-59 Monitor   track for change
  <40   Pass      skip
```

Presets live in `app/routers/clients.py :: SCORING_PRESETS`. The 20-criterion library seeds from `app/seed.py` on first run.

---

## Agents (scheduled background jobs)

See the **Agents** view in the dashboard, or `app/services/scheduler.py` for the code.

| Agent | Schedule | What it does |
|---|---|---|
| **Nightly pipeline rescore** | daily @ 03:00 | Recalculate Matchmaker for every active client. Free. |
| **Weekly behavior profile refresh** | weekly Mon @ 04:00 | Re-infer stale behavior profiles from company type. |
| **Daily pipeline snapshot** | daily @ 02:00 | Capture tier counts + avg Matchmaker per active client. Feeds future analytics. |
| **Nightly HubSpot sync** | daily @ 05:00 | Pull companies from a HubSpot list (set `HUBSPOT_BD_LIST_ID` in `.env`), import new ones, auto-add to active pipelines. Skipped if not configured. |

Each agent can be paused, run now, or inspected from the Agents view.

### Ad-hoc HubSpot import

Top card in the Agents view. Type a search term (`carrier`, `brokerage`, `MGA`, etc.) → pulls matching HubSpot companies, dedupes against existing prospects (including fuzzy matches like "Erie" vs "Erie Insurance"), imports new ones into every active client's pipeline.

---

## Stability

- **Tests**: `bash scripts/run_tests.sh` — 47 tests covering scoring math, client sync, presets, pipeline ops, agents, and health endpoints
- **Backups**: nightly SQLite snapshots at `data/backups/pipeline-YYYYMMDD.db`, 14-day retention, managed by `app/services/backup.py`
- **Logging**: structured JSON logs at `data/logs/app.log` + errors-only at `data/logs/errors.log`. Rotated at 10 MB / 5 MB.
- **Error dashboard**: `GET /api/health/errors` returns the last 100 errors from an in-memory ring buffer
- **Migrations**: Alembic at `alembic/`. To add a schema change: edit `app/models.py`, run `alembic revision --autogenerate -m "description"`, review, `alembic upgrade head`

---

## File structure

```
PipelineBuild/
├── app/
│   ├── main.py              FastAPI entry, startup, migrations, exception handler
│   ├── database.py          SQLAlchemy engine + session
│   ├── models.py            ORM models (clients, prospects, pipeline_entries, criteria, etc.)
│   ├── schemas.py           Pydantic request/response models
│   ├── scoring.py           4-layer scoring engine (PMF, Matchmaker, tiers, friction, intent)
│   ├── seed.py              First-run seed data (criteria library, seed companies)
│   ├── logging_config.py    Structured logging setup
│   ├── routers/
│   │   ├── clients.py       Client CRUD, criteria mgmt, presets, lens-options, delete-everywhere
│   │   ├── prospects.py     Prospect CRUD, bulk import, cascade-delete
│   │   ├── pipeline.py      Pipeline entries, scoring, breakdown endpoint, overrides
│   │   ├── relationships.py RS updates, 5-source scan
│   │   ├── intros.py        Intro generation, cost-gated
│   │   ├── activity.py      Activity feed
│   │   ├── behavior.py      Behavior profiles + type→behavior map
│   │   ├── intent.py        Intent signals
│   │   ├── filters.py       Identity filters + live preview
│   │   ├── notifications.py Pending-action approval flow
│   │   ├── profiles.py      Business profiles (3-layer generation)
│   │   └── schedules.py     Agents API + ad-hoc HubSpot import
│   └── services/
│       ├── claude_ai.py     Claude API: profiling, scoring, intro gen, parsing
│       ├── hubspot_scan.py  HubSpot REST API: search, contacts, list memberships
│       ├── apollo_enrich.py Apollo REST API
│       ├── gmail_scan.py    Gmail OAuth (stub)
│       ├── calendar_scan.py Google Calendar OAuth (stub)
│       ├── profile_generator.py  Business profile 3-layer generation
│       ├── type_inference.py Free type inference from HubSpot + Apollo + keywords
│       ├── scheduler.py     Agent layer scheduler + built-in jobs
│       └── backup.py        SQLite backup service
├── alembic/                 Schema migrations
├── tests/                   pytest suite (47 tests)
├── static/
│   ├── index.html           Dashboard SPA shell
│   └── app.js               Alpine.js app logic
├── data/
│   ├── pipeline.db          SQLite database (not in git)
│   ├── backups/             Nightly snapshots (not in git)
│   └── logs/                Rotating logs (not in git)
├── scripts/
│   ├── run_tests.sh         Test runner
│   └── setup_launchagent.sh LaunchAgent installer
├── docs/
│   └── SCORING_ARCHITECTURE.md
├── .env                     API keys (NOT COMMITTED)
├── .env.example             Template
├── requirements.txt
└── run.sh                   One-command startup
```

---

## Extending

**Add a new agent (scheduled job):**
1. Write a function in `app/services/scheduler.py` that takes a `db` session and returns a dict
2. Register it in `JOB_REGISTRY` with a unique key, name, description, and schedule
3. Restart the server — the row seeds automatically

**Add a new scoring criterion:**
- Toggle an existing one from the library (Scoring Criteria panel in the UI)
- Or add a new library entry in `app/seed.py :: _seed_criteria_library()` and re-seed

**Add a new data source for relationship scans:**
- Create `app/services/<source>_scan.py` returning `{hits: int, details: list}`
- Wire into the scan sequence in `app/routers/relationships.py`

**Add a new company type:**
- Update `TYPE_BEHAVIOR_MAP` in `app/routers/behavior.py` with default behavior values
- Add the type to the dropdown in `static/index.html` (Profile tab)

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.9, FastAPI, SQLAlchemy 2.0 |
| Database | SQLite |
| Frontend | HTML, Tailwind CDN, Alpine.js CDN (no build step) |
| AI | Anthropic Claude API (claude-sonnet-4-5) |
| Migrations | Alembic |
| Tests | pytest + FastAPI TestClient |
| Server | Uvicorn |

---

## Voice rules (for AI-generated content)

All Claude-generated content (intros, profile summaries) respects these rules from `CLAUDE.md`:

- No em dashes
- No banned words: *passionate, leveraged, architected, seamless, scalable, dynamic*
- No AI-sounding phrases: *delve into, it's worth noting, let's unpack, in today's landscape, it goes without saying, at the end of the day*
- Conversational, direct, specific numbers over "many"
- Short sentences, short paragraphs

The Intro tab's voice checker flags violations live as you edit.
