# BD Pipeline Agent: Build Playbook
## How This Was Built From Scratch in One Session
**Author:** Vinnie Garth, Vinsational Consulting
**Built:** April 17, 2026
**Tool:** Claude Code (Anthropic)

---

## What Got Built

A fully autonomous BD pipeline scoring agent that runs locally on a Mac. It takes prospect companies, scores them against client-specific criteria using a 4-layer deal probability engine, ranks them by Matchmaker Score, and generates introduction packages. It watches Gmail for new companies, rescores daily, and alerts when tiers shift. All scoring runs for free using a heuristic engine. Claude API features are optional and cost-gated with explicit user approval.

---

## The Build Sequence

This playbook documents the exact order of operations. Each step built on the previous one. The whole thing was built conversationally with Claude Code in a single session.

---

### STEP 1: Write the Build Spec First

Before touching Claude Code, wrote a detailed build spec document (`BD_Pipeline_Agent_Build_Spec.md`) covering:
- What the app does (the core loop)
- All 9 database tables with SQL schemas
- API integration details (Gmail, HubSpot, Calendar, Apollo, Claude)
- The scoring formula (Matchmaker Score = PMF * W1 + RS * W2)
- Five-source relationship scan sequence
- Dashboard UI mockups (6 views described)
- Claude API prompts (5 prompts, word for word)
- MVP scope broken into 4 phases
- Seed data inventory
- Success criteria

Also bundled supporting files into a zip:
- Company profile template (with Tivly already filled in)
- Scoring methodology doc
- Relationship map
- Guidewire ecosystem CSV (30 pre-scored partners)
- AIR 2025 conference attendees PDF
- Command reference
- Agent skill definition

**Lesson learned:** The spec took longer to write than the code took to build. But the spec is what made the build possible in one session. Claude Code had everything it needed without me re-explaining.

---

### STEP 2: Choose the Stack

**Decision:** Python (FastAPI) over Node.js
- Python 3.9 was already installed on the Mac
- Node.js was not installed, and no brew/npm available
- FastAPI is lighter for data-heavy scoring logic
- Claude API SDK is cleaner in Python

**Decision:** HTML + Tailwind CDN + Alpine.js over React
- No Node.js means no React build step
- Alpine.js provides reactive data binding via CDN (no install)
- Tailwind via CDN (no build step)
- Tradeoff: less ergonomic than JSX, but zero setup friction

**Decision:** SQLite over PostgreSQL
- Single user, local app
- Zero configuration
- Database is one file (`pipeline.db`)
- Can migrate to Postgres later if needed

---

### STEP 3: Build the Foundation (Phase 1)

Built 5 files:
1. `requirements.txt` - Python dependencies
2. `app/database.py` - SQLAlchemy engine pointing at SQLite
3. `app/models.py` - All ORM models (started with 10 tables)
4. `app/schemas.py` - Pydantic validation models
5. `app/main.py` - FastAPI app with CORS, static file serving, DB init

**Key decision:** Used `Base.metadata.create_all()` on startup instead of Alembic migrations. For a local SQLite app, this is simpler. Added raw `ALTER TABLE` statements for schema evolution later.

---

### STEP 4: Build the Scoring Engine

Created `app/scoring.py` with three functions:
- `calculate_pmf()` - Weighted criteria normalized to 0-100
- `calculate_matchmaker()` - Combined PMF + RS formula
- `assign_tier()` - Hot/Warm/Monitor/Pass classification

**This file was rewritten 3 times** as the scoring model evolved from a 2-factor formula to a 4-layer engine. Each rewrite kept backwards compatibility.

---

### STEP 5: Build API Routes (6 Routers)

Built one router file per domain:
- `clients.py` - CRUD + criteria management
- `prospects.py` - CRUD + bulk import + CSV upload
- `pipeline.py` - Scoring, ranking, filtering, CSV export
- `relationships.py` - RS management + 5-source scan
- `intros.py` - Intro package generation
- `activity.py` - Activity feed

**Pattern:** Every router follows the same structure. CRUD operations, then domain-specific logic. Consistent return shapes.

---

### STEP 6: Seed the Database

Created `app/seed.py` to auto-import on first run:
- Tivly client with full profile
- 4 scoring criteria for Tivly
- 16 companies from Scott Montgomery's email
- 30 Guidewire ecosystem partners (pre-scored from CSV)
- 6 known relationships with RS scores
- 5 AIR 2025 conference attendees

**Key insight:** The Guidewire CSV had pre-scored criterion values. Imported those directly into `criterion_scores` so 30 companies were fully scored from the start.

**Problem:** The AIR 2025 attendees PDF was image-based (scanned). Couldn't parse it with standard Python. Seeded only the 5 known attendees from relationship data. Full PDF import left as future enhancement (needs OCR).

---

### STEP 7: Build the Dashboard

Two files: `static/index.html` (SPA shell) and `static/app.js` (Alpine.js application logic).

**First version (v1):** Simple table with client dropdown, weight preset, summary cards, ranked pipeline, detail slide panel with 4 tabs.

**Upgrade to v2:** Added three-layer control system (Client, Sources, Weights), collapsible criteria panel, identity filters panel, tier filter buttons, quick-add bar, bulk select checkboxes, remove buttons, toast notifications.

**Lesson:** Building the UI without Node.js worked fine. Alpine.js + Tailwind CDN is surprisingly capable for a dashboard like this. The tradeoff is no component reuse across files, but with a single-page app that's not a problem.

---

### STEP 8: Add Client Management Features

**Problem:** Only Tivly was in the client dropdown. Needed a way to add new clients dynamically.

**Solution evolved through 3 iterations:**

1. **First:** Simple modal with text input + Claude API research
2. **Second:** Smart search modal querying HubSpot + Apollo + manual fallback (3 paths to add a client)
3. **Third:** Grouped dropdown showing all prospects as selectable clients. Click any prospect to promote it to a client with auto-profiling and criteria generation.

**Key decision:** Made the client dropdown show ALL companies in the database, not just formal clients. Any company can become a scoring client with one click. The list grows automatically as you import more companies.

---

### STEP 9: Build Free Scoring (Heuristic Engine)

**Problem:** Scoring required Claude API calls ($0.01-0.03 per company). With 47 companies, that's $0.50-1.50 per scoring run. User wanted zero cost.

**Solution:** Built a rule-based heuristic scorer in `scoring.py`:
- Matches prospect metadata (type, industry, business model, stage, description) against criterion keywords
- Uses logical rules per criterion category (distribution, SMB focus, digital CX, lead gen, etc.)
- Falls back to keyword matching for unknown criteria
- Generates reasoning strings ("Good fit | Type: Technology | Vertical: InsurTech | Stage: growth (heuristic)")

**Result:** All 47 companies score instantly, for free. Scores are directional (not perfect), but they rank sensibly. Users can override individual scores manually.

Also added `_generate_default_criteria()` as a fallback when Claude API fails to generate criteria. Creates 5 generic criteria based on company type detection.

---

### STEP 10: Upgrade to 4-Layer Scoring

**Problem:** Linear 2-factor formula (PMF + RS) was too simple. Didn't account for behavioral mismatches or timing.

**Solution:** Upgraded to a 4-layer deal probability engine:

1. **Identity Filter** (hard gate) - Reject companies that don't match business model, stage, or vertical requirements
2. **Capability Score** (PMF, 0-100) - Weighted criteria from the library
3. **Behavioral Friction** (0.5-1.0 coefficient) - Penalizes mismatches in sales motion, culture, decision speed
4. **Intent Multiplier** (0.8-2.0x) - Boosts companies with recent hiring, expansion, funding signals

**New formula:** `Matchmaker = min(100, PMF * Friction * Intent + RS_Bonus)`

Added 3 new database tables: `behavior_profiles`, `intent_signals`, `identity_filters`
Added 3 new API routers: `behavior.py`, `intent.py`, `filters.py`
Added 2 new detail panel tabs: Behavior (6th tab), Intent (7th tab)
Added Friction and Intent columns to the pipeline table

---

### STEP 11: Build the Criteria Library

**Problem:** Criteria were generated per client (4-5 each). User wanted to browse and toggle from a library of 20+ options.

**Solution:** Built a master library of 20 criteria organized in 4 groups:
- Market Fit (5 criteria)
- Product & Technology (6 criteria)
- Business Dynamics (5 criteria)
- Relationship & Timing (4 criteria)

Each criterion has: name, description, why it matters, default weight, and heuristic keywords.

**UI:** 4 collapsible group tiles. Click a group to expand. Inside each group, criteria show as toggle tiles (blue = active, gray = inactive). Active tiles show weight sliders. "Rescore" button recalculates the entire pipeline with the current criteria mix.

**Database:** Added `criteria_library` table (20 rows, read-only). Added `library_id`, `active`, and `group_name` columns to `scoring_criteria`.

---

### STEP 12: Build the Cost Gate

**Problem:** User didn't want surprise charges from Claude API calls.

**Solution:** Every action that calls the Anthropic API now queues a `PendingApiAction` record instead of executing immediately. The dashboard shows an alert bar: "1 action needs your approval." User sees the description and estimated cost, then clicks "Approve & Run" or "Skip."

**Cost-gated actions:** Generate Intro Package, Research Intent Signals, Client Profiling
**Free actions (no gate):** All scoring, ranking, filtering, importing, exporting

Added 2 new tables: `notifications`, `pending_api_actions`
Added 1 new router: `notifications.py`
Added alert bar to dashboard HTML
Added approval/reject buttons with real-time notification polling

---

### STEP 13: Build the Agent Layer

**Problem:** The app waited for the user to push buttons. Not an agent.

**Solution:** Created two Claude Code scheduled tasks:

1. **Daily Rescore** (7:03am) - Rescores all pipelines across all clients using the free heuristic engine. Detects tier changes.
2. **Gmail Watcher** (every 8 hours) - Scans Gmail for emails from ANY client contact. Extracts company names. Auto-adds to pipeline. Auto-scores.

Both tasks are free (no API calls). They hit the same localhost:8000 API endpoints the dashboard uses.

---

### STEP 14: Auto-Start on Login

Set up a macOS LaunchAgent (`com.vinsational.bd-pipeline-agent.plist`) that:
- Starts the Uvicorn server automatically on Mac login
- Restarts it if it crashes (KeepAlive)
- Logs to `data/server.log`
- Dashboard is always available at http://localhost:8000

Also created a Desktop launcher (`BD Pipeline Agent.command`) as a manual alternative.

---

## Key Decisions and Why

| Decision | Why |
|----------|-----|
| Python over Node | Already installed, no npm needed, better for data logic |
| Alpine.js over React | No build step, CDN delivery, zero install |
| SQLite over Postgres | Single user, portable, zero config |
| Heuristic scoring over API-only | Zero cost, instant, always available |
| Cost gate over free API access | User controls spending, no surprises |
| LaunchAgent over manual start | Zero friction daily access |
| Criteria library over per-client generation | Browse and toggle beats regenerate every time |
| 4-layer scoring over 2-factor | More dimensions = better signal, same data |

---

## What's Not Built Yet

- Gmail and Calendar OAuth (server-side, not just MCP)
- Full AIR 2025 PDF parsing (needs OCR)
- Relationship map network visualization
- Conference cross-reference view
- Quick-score UI (inline editing in pipeline table)
- CRM sync (push scored pipeline back to HubSpot)
- Multi-user support
- Deployment to cloud (currently localhost only)

---

## How to Replicate This Build

If you wanted to build a similar agent from scratch:

1. **Write the spec first.** Every table, every endpoint, every formula. Don't start coding until the spec is complete.
2. **Bundle your data.** CSVs, PDFs, relationship maps. Have them ready before the build session.
3. **Start with the database and scoring engine.** Get the math right before building UI.
4. **Build API routes before frontend.** Test with curl or /docs before adding HTML.
5. **Seed real data early.** Don't build against empty tables.
6. **Build free first, add paid later.** Heuristic scoring works. API calls are a premium upgrade.
7. **Cost gate everything.** If an action costs money, require explicit approval.
8. **Auto-start the server.** If you have to remember to start it, you won't use it daily.
9. **Schedule the agent tasks last.** The app has to work manually before it works autonomously.

---

## Session Stats

- **Duration:** Single Claude Code session
- **Files created:** 40+
- **Database tables:** 16
- **API endpoints:** 45+
- **Lines of Python:** ~3,000
- **Lines of JavaScript:** ~600
- **Lines of HTML:** ~500
- **Scoring criteria:** 20 in library
- **Seed data:** 47 prospects, 6 relationships, 5 attendees
- **Scheduled tasks:** 2 (daily rescore + Gmail watcher)
- **Anthropic API cost for the build:** $0 (heuristic scoring, no API calls during build)
