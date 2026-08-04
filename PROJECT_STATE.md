# BD Pipeline Agent: Current Project State
## For Gap Analysis
**Generated:** April 17, 2026
**Project Location:** ~/Projects/PipelineBuild/

---

## What This Is

A local web application for managing B2B business development pipelines. Takes prospect companies, scans for existing relationships, scores product-market fit against client-specific criteria, ranks by a combined Matchmaker Score, and generates introduction packages. Built for a solo BD operator managing introductions between clients and prospect companies.

**Stack:** Python 3.9 + FastAPI + SQLite + Alpine.js + Tailwind CSS (CDN)
**Server:** Uvicorn on localhost:8000
**AI:** Anthropic Claude API (claude-sonnet-4-20250514) for profiling, scoring, and content generation. Optional, not required for core functionality.

---

## File Inventory (28 files)

```
PipelineBuild/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, CORS, static mount, DB init, seed on startup
│   ├── database.py             # SQLAlchemy engine (SQLite at data/pipeline.db)
│   ├── models.py               # 10 ORM models (see schema below)
│   ├── schemas.py              # Pydantic request/response models
│   ├── scoring.py              # PMF calculation, Matchmaker formula, tier assignment
│   ├── seed.py                 # First-run import: Tivly, 16 companies, relationships, Guidewire CSV
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── clients.py          # Client CRUD, search (HubSpot+Apollo), promote, Claude profiling, auto-scoring
│   │   ├── prospects.py        # Prospect CRUD, bulk import, CSV upload, available-as-clients list
│   │   ├── pipeline.py         # Pipeline CRUD, scoring, ranking, quick-add, delete, weights, CSV export
│   │   ├── relationships.py    # Relationship CRUD, 5-source scan, RS sync to pipeline
│   │   ├── intros.py           # Intro package generation (Claude or fallback template)
│   │   └── activity.py         # Activity feed with filters
│   └── services/
│       ├── __init__.py
│       ├── claude_ai.py        # Claude API: 5 functions (profile, score, intro, parse email, assess RS)
│       ├── hubspot_scan.py     # HubSpot: company search, contact lookup, relationship scan
│       ├── apollo_enrich.py    # Apollo: org search, company enrichment
│       ├── gmail_scan.py       # STUB: returns empty results
│       └── calendar_scan.py    # STUB: returns empty results
├── static/
│   ├── index.html              # Dashboard SPA (387 lines)
│   └── app.js                  # Alpine.js application logic (556 lines)
├── data/
│   └── pipeline.db             # SQLite database (created on first run)
├── .claude/
│   └── launch.json             # Dev server config for Claude Code preview
├── .env                        # API keys (ANTHROPIC_API_KEY set, others empty)
├── .env.example                # API key template
├── requirements.txt            # fastapi, uvicorn, sqlalchemy, pydantic, anthropic, python-dotenv
├── run.sh                      # One-command startup script
├── ARCHITECTURE.md             # Architecture doc (OUTDATED, does not reflect v2 dashboard)
├── guidewire_ecosystem.csv     # 30 Guidewire partners with pre-scored Tivly fit data
├── 2025_AIR_Conference_Attendees.pdf  # 300+ attendees (image-based PDF, not parseable)
├── BD_Pipeline_Agent_Build_Spec.md    # Original build spec
├── BD_Pipeline_Agent_SKILL.md         # Agent skill definition
├── BD_Pipeline_Agent_COMMANDS.md      # Command reference
├── company_profile_template.md        # Company profile template + Tivly profile
├── scoring_methodology.md             # Scoring formula documentation
├── relationship_map.md                # Relationship entries reference
├── Partner_Ecosystem_Scoring_Workflow.md  # Original workflow documentation
├── QUICK_START.md                     # User-facing command reference
└── SYSTEM_INSTRUCTIONS.md            # System instructions reference
```

---

## Database Schema (10 Tables)

### clients
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| name | String | Company name |
| website | String | URL |
| description | Text | What they do |
| primary_revenue_driver | Text | Main product/service |
| target_buyer | Text | ICP |
| profile_json | Text | Full profile as JSON blob |
| created_at / updated_at | DateTime | Timestamps |

### scoring_criteria
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| client_id | FK -> clients | |
| name | String | Criterion name |
| description | Text | What it measures |
| why_it_matters | Text | Connection to client value prop |
| weight | Integer | 1-10 importance |
| sort_order | Integer | Display order |

### prospects
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| name | String | Company name |
| type | String | "Regional Carrier", "Technology", etc. |
| website, domain | String | |
| alternate_domains | Text | JSON array |
| hq_city, hq_state | String | |
| employees | Integer | |
| revenue | String | |
| description | Text | |
| decision_makers_json | Text | JSON array of contacts |
| enrichment_source | String | "apollo", "hubspot", "manual" |
| enrichment_date | DateTime | |

### pipeline_entries
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| client_id | FK -> clients | |
| prospect_id | FK -> prospects | |
| source | String | How this company entered the pipeline |
| source_date | Date | |
| source_priority | String | "first-mentioned" or "standard" |
| tier | String | "hot", "warm", "monitor", "pass", "unscored" |
| pmf_score | Float | 0-100 |
| relationship_score | Integer | 0-5 |
| matchmaker_score | Float | 0-100 |
| pmf_weight | Float | Default 0.6 |
| rs_weight | Float | Default 0.4 |
| status | String | "new", "scored", "outreach_sent", "meeting_set", "intro_made" |
| next_action | Text | |
| notes | Text | |
| UNIQUE | | (client_id, prospect_id) |

### criterion_scores
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| pipeline_entry_id | FK -> pipeline_entries | |
| criterion_id | FK -> scoring_criteria | |
| score | Integer | 0-5 |
| reasoning | Text | AI-generated or manual |

### relationships
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| prospect_id | FK -> prospects | |
| contact_name, contact_title, contact_email, contact_linkedin | String | |
| score | Integer | 0-5 relationship strength |
| context | Text | How you know them |
| source | String | "gmail", "hubspot", "calendar", "conference", "manual" |
| last_touch | Date | |
| warmest_path | String | Best intro route |

### relationship_scans
Per-source hit counts and JSON detail blobs for each scan run. Columns: gmail_hits/details, hubspot_hits/details, calendar_hits/details, conference_hits/details, relationship_map_hits/details, final_rs, evidence_summary.

### intro_packages
Email subject, body, talking points (JSON), value props (prospect + client), mutual connections (JSON), objections (JSON), status (draft/sent), sent_date.

### activity_log
Pipeline_entry_id (nullable), action, old_value, new_value, notes, created_at.

### conference_attendees
Conference_name, attendee_name, title, company, city, state.

---

## API Endpoints (37 total)

### Clients (14 endpoints)
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/clients | List all clients |
| GET | /api/clients/criteria-counts | Map of client_id -> criteria count |
| GET | /api/clients/search?q= | Search HubSpot + Apollo for companies |
| POST | /api/clients | Create client |
| POST | /api/clients/from-source | Create from search result + Claude profiling + auto-score pipeline |
| POST | /api/clients/research?name= | Create + research (older endpoint) |
| POST | /api/clients/promote/{prospect_id} | Promote prospect to client + auto-score |
| GET | /api/clients/{id} | Get single client |
| PUT | /api/clients/{id} | Update client |
| DELETE | /api/clients/{id} | Delete client + criteria |
| GET | /api/clients/{id}/criteria | List criteria |
| POST | /api/clients/{id}/criteria | Add criterion |
| PUT | /api/clients/{id}/criteria/{cid} | Update criterion |
| DELETE | /api/clients/{id}/criteria/{cid} | Delete criterion |

### Prospects (7 endpoints)
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/prospects | List/search prospects |
| GET | /api/prospects/available-as-clients | Prospects not yet clients |
| POST | /api/prospects | Create single |
| POST | /api/prospects/bulk | Create from name list |
| POST | /api/prospects/import-csv | Upload CSV |
| GET | /api/prospects/{id} | Get single |
| PUT | /api/prospects/{id} | Update |

### Pipeline (12 endpoints)
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/pipeline/{client_id} | Ranked list with filters (tier, status, RS, PMF) and sort |
| POST | /api/pipeline | Create single entry |
| POST | /api/pipeline/bulk | Create multiple entries |
| POST | /api/pipeline/quick-add | Add by company name (creates prospect if needed) |
| DELETE | /api/pipeline/{entry_id} | Remove single entry |
| DELETE | /api/pipeline/bulk/{client_id} | Remove multiple entries |
| POST | /api/pipeline/{entry_id}/score | Score with criterion scores |
| POST | /api/pipeline/{client_id}/score-all | Recalculate all Matchmaker scores |
| PUT | /api/pipeline/{entry_id} | Update status/notes/next_action |
| PUT | /api/pipeline/{client_id}/weights | Change PMF/RS weights + rescore |
| GET | /api/pipeline/{client_id}/summary | Tier counts + averages |
| GET | /api/pipeline/{entry_id}/scores | Criterion scores for one entry |
| GET | /api/pipeline/{client_id}/export | CSV download |

### Relationships (5 endpoints)
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/relationships/{prospect_id} | List relationships |
| POST | /api/relationships | Create/upsert relationship |
| PUT | /api/relationships/{id} | Update relationship |
| POST | /api/relationships/{prospect_id}/scan | Run 5-source scan |
| GET | /api/relationships/scans/{prospect_id} | Scan history |

### Intros (4 endpoints)
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/intros/generate/{entry_id} | Generate intro package |
| GET | /api/intros/drafts | Draft Tracker: all intro packages across pipelines (latest per entry) with client/prospect/tier context, filterable by status + client_id |
| GET | /api/intros/{entry_id} | Get existing package |
| PUT | /api/intros/{id} | Update/mark sent |

### Activity (2 endpoints)
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/activity | Global feed with filters |
| GET | /api/activity/{entry_id} | Per-entry activity |

### Utility (2 endpoints)
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/health | Health check + API key status |
| GET | / | Redirect to dashboard |

---

## Dashboard UI

### Three-Layer Control System
1. **Layer 1: Client** - Grouped dropdown (Active Clients with criteria count + All Companies from prospects table). Selecting a prospect auto-promotes to client with Claude profiling + criteria generation + pipeline auto-population + auto-scoring. "+ New" button opens search modal (HubSpot + Apollo + manual fallback).

2. **Layer 2: Data Sources** - Checkboxes for 5 sources (Gmail stub, HubSpot, Calendar stub, Conference Lists, Relationship Map). Shows Active/Stub status per source.

3. **Layer 3: Scoring Weights** - Preset dropdown (60/40, 80/20, 50/50, 30/70, Custom). PMF/RS sliders with inverse coupling. Changes trigger pipeline rescore.

### Collapsible Criteria Panel
Grid of criteria cards with weight sliders (1-10), delete on hover, add new criterion text input. Weight changes trigger pipeline rescore.

### Pipeline Table
Quick-add bar, Score All button, CSV export, tier filter buttons, select-all checkbox, per-row remove button, sortable columns (Company, PMF, RS, Matchmaker), tier badges (color-coded).

### Draft Tracker View
Nav view ("Drafts") listing every intro email across the pipeline with status summary tiles (All/Draft/Approved/Sent) that double as filters. Rows show prospect, client, contact, subject, tier, Matchmaker Score, status, and last-updated; clicking a row jumps to that pipeline entry's Intro tab. Scopes to the active client and refreshes on demand.

### Detail Slide Panel
4 tabs (Scoring, Contacts, Intro, Activity). "Make Client" button for prospects not yet clients. "Remove" button. Intro generation with Claude or fallback template.

### Modals
- New Client: Smart search (HubSpot + Apollo), manual entry fallback
- Import: Paste company names, bulk add

### Toast Notifications
Bottom-right toast for confirmations (4s auto-dismiss).

---

## Scoring Engine

```
Matchmaker Score = (PMF * W1) + ((RS / 5 * 100) * W2)
Default: W1 = 0.6, W2 = 0.4

PMF = (sum of (criterion_score/5 * weight)) / (sum of weights) * 100

Tiers:
  70+   = Hot
  50-69 = Warm
  30-49 = Monitor
  <30   = Pass
```

### Auto-Scoring Flow (on new client creation)
1. Claude profiles the company
2. Claude generates 4-6 scoring criteria
3. All prospects added to pipeline
4. Claude scores each prospect against each criterion (0-5 with reasoning)
5. PMF, Matchmaker, and tier calculate automatically
6. Fallback: baseline score of 2/5 per criterion if Claude API unavailable

---

## External Service Integration Status

| Service | Status | Requires | What It Does |
|---------|--------|----------|--------------|
| Claude API | WORKING | ANTHROPIC_API_KEY | Profiling, scoring, intro gen, email parsing, RS assessment |
| HubSpot | IMPLEMENTED (needs key) | HUBSPOT_API_KEY | Company search, contact lookup, relationship scan |
| Apollo.io | IMPLEMENTED (needs key) | APOLLO_API_KEY | Org search, company enrichment |
| Gmail | STUB | OAuth setup | Email thread search for relationship evidence |
| Google Calendar | STUB | OAuth setup | Meeting history for relationship evidence |

---

## Seed Data (loaded on first run)

| Data | Count | Source File |
|------|-------|-------------|
| Tivly client | 1 | company_profile_template.md |
| Tivly scoring criteria | 4 | Build spec |
| Scott Montgomery prospects | 16 | Build spec |
| Guidewire ecosystem prospects | 30 | guidewire_ecosystem.csv |
| Known relationships | 6 | relationship_map.md |
| Conference attendees (AIR 2025) | 5 | Known entries from relationships |
| Pipeline entries (Tivly) | 46 | Auto-created from prospects |

---

## Known Gaps and Open Items

### Scoring Without API Cost
- **OPEN:** User requested free scoring without Claude API calls. Plan: type-based heuristic auto-scoring (use company type to assign default scores) + quick-score UI for manual overrides. NOT YET BUILT.

### Data Sources
- Gmail scan is a stub. Needs Google OAuth implementation.
- Calendar scan is a stub. Needs Google OAuth implementation.
- HubSpot and Apollo services are implemented but require paid API keys.
- Source layer checkboxes in UI are visual only. They don't yet filter which sources are used in relationship scans.

### Conference Attendees
- Only 5 known attendees seeded. The AIR 2025 PDF (300+ attendees) is image-based and not parseable without OCR. No OCR library is installed.

### UI/UX Gaps
- No inline editing of criterion scores in the pipeline table (must open detail panel).
- No relationship map visualization (network graph view from spec).
- No conference cross-reference view (upload + auto-match from spec).
- ARCHITECTURE.md is outdated and does not reflect the v2 dashboard.
- No "Regenerate Profile" button for clients whose Claude profiling failed.
- Source layer checkboxes don't functionally toggle source usage yet.

### Pipeline Management
- When a new prospect is quick-added, it only joins the ACTIVE client's pipeline. It should be added to ALL client pipelines.
- Bulk delete endpoint exists but frontend uses individual deletes in a loop.
- No undo for removals.

### Scoring Engine
- Score-all recalculates from existing criterion_scores but doesn't generate NEW criterion scores for unscored entries (that requires Claude API).
- No type-based heuristic scoring fallback yet.
- No quick-score UI for manual scoring.

### Multi-Client
- Cross-client opportunity detection not built ("this company fits both Tivly AND Circle AI").
- No per-client pipeline isolation toggle.

### Automation
- No periodic Gmail scan.
- No score change alerts.
- No scheduled re-scoring.

### Export/Integration
- CSV export works for pipeline data.
- No CRM sync (push scored pipeline back to HubSpot).
- No email integration (auto-send intros from the app).

---

## How to Run

```bash
cd ~/Projects/PipelineBuild
bash run.sh
# Or double-click "BD Pipeline Agent.command" on Desktop
# Dashboard: http://localhost:8000
# API docs: http://localhost:8000/docs
```

---

## Dependencies

```
fastapi==0.111.0
uvicorn[standard]==0.30.1
sqlalchemy==2.0.30
pydantic==2.7.3
anthropic==0.28.0
python-dotenv==1.0.1
python-multipart==0.0.9
```

Python 3.9.6 (system). No Node.js. No brew.
