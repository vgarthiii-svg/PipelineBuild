# BD Pipeline Agent: Architecture v2
## Complete System Diagram
**Updated:** April 17, 2026

---

## System Overview

```
+============================================================================+
|                        BD PIPELINE AGENT                                    |
|                     Autonomous BD Scoring System                            |
+============================================================================+
|                                                                             |
|  +---------------------------+    +-------------------------------+         |
|  |     SCHEDULED AGENTS      |    |        BROWSER DASHBOARD      |         |
|  |  (Claude Code Tasks)      |    |  http://localhost:8000         |         |
|  |                           |    |                               |         |
|  | Daily Rescore (7am)       |    |  Layer 1: Client Selector     |         |
|  |   - Free, heuristic       |    |  Layer 2: Data Sources        |         |
|  |   - All clients           |    |  Layer 3: Scoring Weights     |         |
|  |   - Detects tier changes  |    |  Criteria Library (20 tiles)  |         |
|  |                           |    |  Identity Filters             |         |
|  | Gmail Watcher (8hr)       |    |  Pipeline Table               |         |
|  |   - Free, reads inbox     |    |  Detail Panel (7 tabs)        |         |
|  |   - All client contacts   |    |  Alert Bar + Cost Gate        |         |
|  |   - Auto-ingests names    |    |                               |         |
|  +---------------------------+    +-------------------------------+         |
|              |                                 |                            |
|              |            HTTP / JSON           |                            |
|              +----------------+----------------+                            |
|                               |                                             |
|  +-----------------------------------------------------------+             |
|  |                    FastAPI (Python 3.9)                     |             |
|  |                    Port 8000 / Uvicorn                      |             |
|  |                                                             |             |
|  |  ROUTERS (10):                                              |             |
|  |  /api/clients        Client CRUD, search, promote, library  |             |
|  |  /api/prospects      Prospect CRUD, bulk import, CSV        |             |
|  |  /api/pipeline       Score, rank, filter, add/remove, export|             |
|  |  /api/relationships  RS updates, 5-source scan              |             |
|  |  /api/intros         Intro package gen (cost-gated)         |             |
|  |  /api/activity       Activity feed                          |             |
|  |  /api/behavior       Behavior profiles (friction layer)     |             |
|  |  /api/intent         Intent signals (multiplier layer)      |             |
|  |  /api/filters        Identity hard filters                  |             |
|  |  /api/notifications  Alerts + pending action approvals      |             |
|  +-----------------------------------------------------------+             |
|              |                          |                                   |
|     +----------------+          +------------------+                        |
|     |    SQLite DB    |          |    SERVICES      |                        |
|     |  pipeline.db    |          |                  |                        |
|     |                 |          | Claude AI [$$$]  |                        |
|     | 13 tables       |          |   Cost-gated     |                        |
|     | (see schema)    |          |   Needs approval |                        |
|     |                 |          |                  |                        |
|     |                 |          | HubSpot [stub]   |                        |
|     |                 |          | Apollo [stub]    |                        |
|     |                 |          | Gmail [stub]     |                        |
|     |                 |          | Calendar [stub]  |                        |
|     +----------------+          +------------------+                        |
|                                                                             |
+============================================================================+
```

---

## 4-Layer Scoring Engine

```
LAYER 1: IDENTITY FILTER (hard gate)
+--------------------------------------------------+
| Allowed business models?  [B2B, SaaS, hybrid]     |
| Allowed stages?           [growth, mature, ent.]   |
| Employee range?           [10 - 50,000]            |
| Excluded verticals?       [Life, Health]           |
|                                                    |
| PASS --> continue to Layer 2                       |
| FAIL --> tier = "filtered", skip scoring           |
+--------------------------------------------------+
                        |
                        v
LAYER 2: CAPABILITY SCORING (PMF, 0-100)
+--------------------------------------------------+
| 20 criteria in 4 groups (toggle on/off per client) |
|                                                    |
| Market Fit (5):        Geographic Overlap          |
|                        Buyer Persona Match         |
|                        Customer Segment            |
|                        Vertical Specialization     |
|                        SMB Commercial Focus        |
|                                                    |
| Product & Tech (6):   Product Complementarity      |
|                        API / Integration           |
|                        Tech Stack Compatibility    |
|                        Data & Analytics            |
|                        Digital CX / Acquisition    |
|                        Lead Gen Compatibility      |
|                                                    |
| Business Dynamics (5): Distribution Alignment      |
|                        Revenue Model               |
|                        Partnership Track Record    |
|                        Competitive Position        |
|                        Regulatory Footprint        |
|                                                    |
| Relationship (4):     Decision Maker Access        |
|                        Sales Cycle Alignment       |
|                        Strategic Priority Fit      |
|                        Conference Proximity        |
|                                                    |
| Each criterion: scored 0-5, weighted 1-10          |
| PMF = (sum of score/5 * weight) / (sum weights)   |
| Normalized to 0-100                                |
+--------------------------------------------------+
                        |
                        v
LAYER 3: BEHAVIORAL FRICTION (coefficient 0.5-1.0)
+--------------------------------------------------+
| Compare CLIENT behavior vs PROSPECT behavior:     |
|   Sales motion     (transactional/consultative/ent)|
|   Partner model    (self-serve/managed/co-sell)    |
|   Decision speed   (fast/moderate/bureaucratic)    |
|   Culture          (innovation/balanced/legacy)    |
|   Customer segment (SMB/mid-market/enterprise)     |
|                                                    |
| Perfect match = 1.0 (no friction)                  |
| Major mismatch = 0.5 (50% penalty)                |
+--------------------------------------------------+
                        |
                        v
LAYER 4: INTENT MULTIPLIER (0.8x - 2.0x)
+--------------------------------------------------+
| Recent signals in last 90 days:                    |
|   Hiring          (BD/channel/partnership roles)   |
|   Expansion       (new states, new products)       |
|   Funding         (rounds, M&A)                    |
|   Partnerships    (announced deals)                |
|   Strategic       (leadership statements)          |
|   Product Launch  (new capabilities)               |
|                                                    |
| No signals = 0.8x (stale penalty)                 |
| High-urgency recent signals = up to 2.0x          |
+--------------------------------------------------+
                        |
                        v
FINAL CALCULATION:
+--------------------------------------------------+
| Adjusted = PMF * Friction * Intent                 |
| RS Bonus = (Relationship Score / 5) * 20           |
| Matchmaker Score = min(100, Adjusted + RS_Bonus)   |
|                                                    |
| TIERS:                                             |
|   80+  = Hot      (priority outreach)              |
|   60-79 = Warm    (secondary outreach)             |
|   40-59 = Monitor (track for changes)              |
|   <40  = Pass     (skip for now)                   |
|   filtered = Hard-filtered by identity             |
+--------------------------------------------------+
```

---

## Cost Gate System

```
USER CLICKS ACTION THAT NEEDS CLAUDE API
              |
              v
+----------------------------------+
| Is ANTHROPIC_API_KEY set?        |
|   NO --> Use free fallback       |
|          (template/heuristic)    |
|   YES --> Continue               |
+----------------------------------+
              |
              v
+----------------------------------+
| Create PendingApiAction record   |
| - action_type                    |
| - description                    |
| - estimated_cost                 |
| - status = "pending"             |
+----------------------------------+
              |
              v
+----------------------------------+
| Create Notification              |
| "Action requires approval"       |
| Alert bar appears on dashboard   |
+----------------------------------+
              |
              v
+----------------------------------+
| USER SEES ALERT BAR              |
| "1 Action needs your approval"   |
|                                  |
| Description of what will happen  |
| Estimated cost: $0.02-0.05      |
| "This will call Anthropic API"   |
|                                  |
| [Skip]     [Approve & Run]       |
+----------------------------------+
       |              |
       v              v
   REJECTED       APPROVED
   No API call    API executes
   No cost        Cost incurred
```

**Cost-gated actions:**
| Action | Trigger | Est. Cost |
|--------|---------|-----------|
| Generate Intro Package | "Generate Intro" button in detail panel | $0.02-0.05 |
| Research Intent Signals | "Research with AI" button in Intent tab | $0.02-0.04 |
| Client Profiling | Creating new client with Claude research | $0.03-0.06 |

**Free actions (no gate needed):**
- All scoring (heuristic engine)
- Pipeline ranking and filtering
- Adding/removing companies
- Weight changes and rescoring
- Behavior profile editing
- Manual intent signal entry
- CSV export
- Gmail watching
- Daily rescore

---

## Database Schema (13 Tables)

```
clients ─────────────────── scoring_criteria ──── criteria_library
  |                              |                     (20 master
  |-- identity_filters           |                      criteria)
  |                              |
  +-- pipeline_entries ──── criterion_scores
  |       |
  |       |-- intro_packages
  |       |-- activity_log
  |
prospects
  |-- behavior_profiles
  |-- intent_signals
  |-- relationships
  |-- relationship_scans

conference_attendees (standalone)
notifications (standalone)
pending_api_actions (standalone)
```

### Table Details

| Table | Rows (seed) | Purpose |
|-------|-------------|---------|
| clients | 1 (Tivly) | Companies you sell on behalf of |
| criteria_library | 20 | Master library of scoring criteria in 4 groups |
| scoring_criteria | 4+ per client | Active/inactive criteria with weights per client |
| prospects | 47 | Companies being evaluated |
| pipeline_entries | 46+ per client | Prospect-client scoring pairs |
| criterion_scores | ~4-20 per entry | Individual criterion scores per pipeline entry |
| relationships | 6 | Known contacts at prospect companies |
| relationship_scans | on demand | 5-source scan results |
| behavior_profiles | 1 (Tivly) | Behavioral attributes for friction scoring |
| intent_signals | 0 | Timing/urgency signals for intent multiplier |
| identity_filters | 1 (Tivly) | Hard-filter rules per client |
| intro_packages | on demand | Generated outreach emails |
| activity_log | auto | Every score change, status update, action |
| conference_attendees | 5 | AIR 2025 known attendees |
| notifications | auto | Alert system for tier changes and agent activity |
| pending_api_actions | on demand | Cost gate approval queue |

---

## API Endpoints (45+)

### Clients (16 endpoints)
| Method | Path | Description | Cost |
|--------|------|-------------|------|
| GET | /api/clients | List all clients | Free |
| GET | /api/clients/criteria-counts | Criteria count per client | Free |
| GET | /api/clients/library/all | Full 20-criteria library | Free |
| GET | /api/clients/search?q= | Search HubSpot + Apollo | Free* |
| POST | /api/clients | Create client | Free |
| POST | /api/clients/from-source | Create from search + profile + score | Gated |
| POST | /api/clients/research | Create + Claude research | Gated |
| POST | /api/clients/promote/{prospect_id} | Promote prospect to client | Gated |
| POST | /api/clients/{id}/criteria/toggle/{lib_id} | Toggle criterion on/off | Free |
| GET | /api/clients/{id}/criteria | List criteria (active only by default) | Free |
| POST | /api/clients/{id}/criteria | Add criterion | Free |
| PUT | /api/clients/{id}/criteria/{cid} | Update weight | Free |
| DELETE | /api/clients/{id}/criteria/{cid} | Remove criterion | Free |
| GET/PUT/DELETE | /api/clients/{id} | Client CRUD | Free |

### Pipeline (13 endpoints)
| Method | Path | Description | Cost |
|--------|------|-------------|------|
| GET | /api/pipeline/{client_id} | Ranked list with filters | Free |
| POST | /api/pipeline | Create entry | Free |
| POST | /api/pipeline/bulk | Bulk create | Free |
| POST | /api/pipeline/quick-add | Add by name | Free |
| DELETE | /api/pipeline/{id} | Remove entry | Free |
| POST | /api/pipeline/{id}/score | Score single entry | Free |
| POST | /api/pipeline/{client_id}/score-all | Rescore all (4-layer) | Free |
| PUT | /api/pipeline/{id} | Update status | Free |
| PUT | /api/pipeline/{client_id}/weights | Change weights | Free |
| GET | /api/pipeline/{client_id}/summary | Tier counts | Free |
| GET | /api/pipeline/{id}/scores | Criterion scores | Free |
| GET | /api/pipeline/{client_id}/export | CSV download | Free |

### Behavior, Intent, Filters, Notifications
| Method | Path | Description | Cost |
|--------|------|-------------|------|
| GET/POST/PUT | /api/behavior/{prospect_id} | Behavior profile CRUD | Free |
| GET/POST | /api/intent/{prospect_id} | Intent signals CRUD | Free |
| DELETE | /api/intent/{signal_id} | Delete signal | Free |
| POST | /api/intent/{prospect_id}/research | AI research | Gated |
| GET/POST/PUT | /api/filters/{client_id} | Identity filter CRUD | Free |
| GET | /api/notifications | List notifications | Free |
| GET | /api/notifications/count | Unread + pending counts | Free |
| GET | /api/notifications/pending | Pending API actions | Free |
| POST | /api/notifications/pending/{id}/approve | Approve + execute | Triggers cost |
| POST | /api/notifications/pending/{id}/reject | Skip action | Free |
| PUT | /api/notifications/read-all | Mark all read | Free |

---

## Dashboard UI

```
+================================================================+
| BD Pipeline Agent  v2.0        Pipeline | Activity    [+Import] |
+================================================================+
| [ALERT BAR: "1 action needs approval"         [View] [Dismiss]] |
+================================================================+
|                                                                  |
| +--LAYER 1--+  +--LAYER 2--+  +--LAYER 3-------+               |
| | CLIENT     |  | SOURCES   |  | SCORING WEIGHTS|               |
| | [dropdown] |  | [x] Gmail |  | [Default 60/40]|               |
| | [+ New]    |  | [x] HS    |  | PMF [====] 60% |               |
| | Active +   |  | [x] Cal   |  | RS  [====] 40% |               |
| | All Cos    |  | [x] Conf  |  |                |               |
| +------------+  | [x] RelMap|  +----------------+               |
|                 +-----------+                                    |
| +--CRITERIA LIBRARY (7 of 20 active)----------[Rescore]---+     |
| | Market Fit          2 of 5 active              [expand]  |     |
| | Product & Technology 2 of 6 active             [expand]  |     |
| | Business Dynamics    1 of 5 active             [expand]  |     |
| | Relationship & Timing 0 of 4 active            [expand]  |     |
| +----------------------------------------------------------+    |
|                                                                  |
| +--IDENTITY FILTERS (active)---------------------------+        |
| | Business models: [B2B] [SaaS] [hybrid]               |        |
| | Stages: [growth] [mature] [enterprise]                |        |
| | Employees: 10 - (none)  Excluded: Life, Health Ins    |        |
| +------------------------------------------------------+        |
|                                                                  |
| [Quick add company...              ] [+Add] [Score All] [Export] |
|                                                                  |
| [46 Total] [10 Hot] [15 Warm] [5 Monitor] [0 Pass] [16 Unscored]|
|                                                                  |
| [All] [Hot] [Warm] [Monitor] [Pass] [Unscored] [Filtered]       |
|                                                                  |
| # | Company      | Type   | PMF | RS  | Matchmaker | Fric | Int |
| 1 | Bindable     | Tech   | 100 | ... | 100        | -    | -   |
| 2 | Appulate     | Tech   | 100 | ... | 100        | -    | -   |
| ...                                                              |
+==================================================================+

DETAIL PANEL (slide-out, 7 tabs):
+--------------------------------------------+
| COMPANY NAME              [Make Client] [X] |
| PMF: 85  |  RS: 3/5  |  Matchmaker: 72    |
| PMF:85 x F:0.9 x I:1.2 + RS:12            |
|                                             |
| [Scoring] [Contacts] [Intro] [Behavior]     |
| [Intent] [Activity]                         |
|                                             |
| (tab content here)                          |
+--------------------------------------------+
```

---

## Scheduled Agent Tasks

| Task | Schedule | What It Does | Cost |
|------|----------|-------------|------|
| bd-daily-rescore | 7:03am daily | Rescores all pipelines across all clients using heuristic engine. Detects tier changes. | Free |
| bd-gmail-watcher | Every 8 hours | Scans Gmail for emails from any client contact. Extracts company names. Auto-adds to pipeline. Auto-scores. | Free |

---

## File Structure (40 files)

```
~/Projects/PipelineBuild/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, migrations, startup, seed
│   ├── database.py             # SQLAlchemy engine (SQLite)
│   ├── models.py               # 16 ORM models
│   ├── schemas.py              # Pydantic request/response models
│   ├── scoring.py              # 4-layer scoring engine + heuristic scorer
│   ├── seed.py                 # First-run data import + criteria library
│   ├── routers/
│   │   ├── clients.py          # Client CRUD, search, promote, library, auto-score
│   │   ├── prospects.py        # Prospect CRUD, bulk, CSV, available-as-clients
│   │   ├── pipeline.py         # Scoring, ranking, 4-layer formula, export
│   │   ├── relationships.py    # RS, 5-source scan
│   │   ├── intros.py           # Intro gen (cost-gated)
│   │   ├── activity.py         # Activity feed
│   │   ├── behavior.py         # Behavior profiles
│   │   ├── intent.py           # Intent signals (research cost-gated)
│   │   ├── filters.py          # Identity filters
│   │   └── notifications.py    # Alerts + cost gate approvals
│   └── services/
│       ├── claude_ai.py        # Claude API (5 functions, all cost-gated)
│       ├── hubspot_scan.py     # HubSpot company search + contacts
│       ├── apollo_enrich.py    # Apollo org search + enrichment
│       ├── gmail_scan.py       # Stub
│       └── calendar_scan.py    # Stub
├── static/
│   ├── index.html              # Dashboard SPA
│   └── app.js                  # Alpine.js application
├── data/
│   └── pipeline.db             # SQLite database
├── .claude/
│   └── launch.json             # Dev server config
├── .env                        # API keys
├── requirements.txt            # Python deps
├── run.sh                      # Manual startup
├── ARCHITECTURE_v2.md          # This file
├── BUILD_PLAYBOOK.md           # How this was built
└── PROJECT_STATE.md            # Gap analysis reference
```

---

## Startup

The server auto-starts on Mac login via LaunchAgent:
```
~/Library/LaunchAgents/com.vinsational.bd-pipeline-agent.plist
```

Dashboard always available at: **http://localhost:8000**

Logs: `~/Projects/PipelineBuild/data/server.log`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9 + FastAPI 0.111 |
| Database | SQLite via SQLAlchemy 2.0 |
| Frontend | HTML + Tailwind CSS (CDN) + Alpine.js (CDN) |
| AI | Anthropic Claude API claude-sonnet-4-20250514 (optional, cost-gated) |
| Server | Uvicorn 0.30 |
| Agent | Claude Code scheduled tasks |
| Auto-start | macOS LaunchAgent |
