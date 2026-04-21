# BD Pipeline Agent: Architecture

> For a source-by-source trace of how data moves through the system, see [INFORMATION_FLOW.md](INFORMATION_FLOW.md).

## System Overview

A local web application that takes prospect companies, scans for existing relationships, scores product-market fit, ranks by Matchmaker Score, and generates introduction packages. Built for a solo BD operator (Vinnie Garth, Vinsational Consulting) managing introductions between clients and prospect companies.

```
+--------------------------------------------------+
|                    BROWSER                        |
|  Dashboard (HTML + Tailwind CSS + Alpine.js)      |
|  http://localhost:8000                            |
+--------------------------------------------------+
                        |
                   HTTP / JSON
                        |
+--------------------------------------------------+
|               FastAPI (Python 3.9)                |
|                                                   |
|  Routers:                                         |
|  /api/clients      Client CRUD + criteria mgmt   |
|  /api/prospects     Prospect CRUD + bulk import   |
|  /api/pipeline      Scoring, ranking, add/remove  |
|  /api/relationships RS updates + 5-source scan    |
|  /api/intros        Intro package generation      |
|  /api/activity      Activity feed + audit trail   |
+--------------------------------------------------+
          |                       |
    +-----------+         +-------------+
    |  SQLite   |         |  Services   |
    | pipeline  |         |             |
    |   .db     |         | Claude AI   |
    +-----------+         | Gmail*      |
                          | HubSpot*    |
                          | Calendar*   |
                          | Apollo*     |
                          +-------------+
                          * = stub, ready for API keys
```

## Data Flow: The Core Loop

```
1. INGEST                    2. SCAN                      3. SCORE
Company list arrives         Check 5 sources for          Score each company against
(email, paste, CSV)          existing relationships       client-specific criteria
       |                            |                            |
       v                            v                            v
+-------------+             +----------------+           +-------------+
| prospects   |             | relationships  |           | criterion   |
| table       |             | table          |           | _scores     |
+-------------+             | rel_scans      |           | table       |
       |                    +----------------+           +-------------+
       v                            |                            |
+----------------+                  v                            v
| pipeline       |<--- RS score flows in ---+     PMF calculated from
| _entries       |                          |     weighted criteria
| (per client)   |<--- PMF score flows in --+
+----------------+
       |
       v
4. RANK                     5. GENERATE                  6. TRACK
Matchmaker Score =          Intro email + talking         Activity log records
(PMF x 0.6) + (RS x 0.4)   points for Hot companies     every score change,
Assign tier: Hot/Warm/                                    intro sent, tier shift
Monitor/Pass
```

## Database Schema (9 Tables)

```
clients                     scoring_criteria
+------------------+        +------------------+
| id (PK)          |        | id (PK)          |
| name             |<-------| client_id (FK)   |
| website          |        | name             |
| description      |        | description      |
| primary_revenue   |        | why_it_matters   |
| target_buyer     |        | weight (1-10)    |
| profile_json     |        | sort_order       |
+------------------+        +------------------+

prospects                   pipeline_entries
+------------------+        +------------------+
| id (PK)          |        | id (PK)          |
| name             |        | client_id (FK)   |----> clients
| type             |<-------| prospect_id (FK) |
| domain           |        | source           |
| hq_city/state    |        | tier             |
| employees        |        | pmf_score        |
| revenue          |        | relationship_score|
| description      |        | matchmaker_score |
| decision_makers  |        | pmf/rs_weight    |
+------------------+        | status           |
       |                    +------------------+
       |                            |
       v                            v
relationships               criterion_scores
+------------------+        +------------------+
| id (PK)          |        | id (PK)          |
| prospect_id (FK) |        | pipeline_entry_id|
| contact_name     |        | criterion_id (FK)|
| contact_title    |        | score (0-5)      |
| score (0-5)      |        | reasoning        |
| context          |        +------------------+
| source           |
| warmest_path     |        intro_packages
+------------------+        +------------------+
                             | id (PK)          |
relationship_scans           | pipeline_entry_id|
+------------------+         | target_contact   |
| id (PK)          |         | email_subject    |
| prospect_id (FK) |         | email_body       |
| gmail_hits/det   |         | talking_points   |
| hubspot_hits/det |         | value_props      |
| calendar_hits/det|         | objections_json  |
| conference_hits  |         | status           |
| relmap_hits      |         +------------------+
| final_rs         |
| evidence_summary |         activity_log
+------------------+         +------------------+
                             | id (PK)          |
conference_attendees         | pipeline_entry_id|
+------------------+         | action           |
| id (PK)          |         | old_value        |
| conference_name  |         | new_value        |
| attendee_name    |         | notes            |
| title            |         | created_at       |
| company          |         +------------------+
+------------------+
```

## Scoring Engine

```
PRODUCT-MARKET FIT (PMF)                    RELATIONSHIP STRENGTH (RS)
Normalized to 0-100                         Scale 0-5

For each criterion:                         5 = Inner Circle (former employer)
  raw += (score/5) * weight                 4 = Strong (emails + meetings)
  max += weight                             3 = Warm (conference + emails)
                                            2 = Light (1 email, LinkedIn)
PMF = (raw / max) * 100                     1 = Aware (event list, CRM only)
                                            0 = Cold (zero evidence)

                MATCHMAKER SCORE
        (PMF * W1) + ((RS/5 * 100) * W2)
        Default: W1=0.6, W2=0.4

                    TIERS
        70+  = Hot     (priority outreach)
        50-69 = Warm    (secondary outreach)
        30-49 = Monitor (track for changes)
        <30  = Pass    (skip for now)
```

## Five-Source Relationship Scan

```
For each prospect company, check IN ORDER:

Source 1: Gmail            from:@{domain} OR to:@{domain}
                           Filter out noreply/marketing/system emails
                           Extract: contact name, subject, date

Source 2: HubSpot          Search contacts/companies by name
                           Extract: contact records, last activity

Source 3: Google Calendar   fullText="{company}" over 2 years
                           Extract: event name, date, attendees

Source 4: Conference DB     Query conference_attendees table
                           Match by company name
                           Extract: attendee name, title, conference

Source 5: Relationship Map  Query relationships table
                           Existing contacts and scores

Result: RS score (0-5) + evidence summary + best contact + warmest path
```

## File Structure

```
PipelineBuild/
|
+-- app/
|   +-- main.py              FastAPI app, startup, static files
|   +-- database.py          SQLAlchemy engine + session
|   +-- models.py            9 ORM models (all tables above)
|   +-- schemas.py           Pydantic request/response models
|   +-- scoring.py           PMF, Matchmaker, tier calculations
|   +-- seed.py              First-run data import
|   |
|   +-- routers/
|   |   +-- clients.py       GET/POST/PUT clients + criteria
|   |   +-- prospects.py     GET/POST/PUT/bulk/CSV import
|   |   +-- pipeline.py      GET/POST/PUT/DELETE, scoring,
|   |   |                    quick-add, bulk ops, CSV export
|   |   +-- relationships.py GET/POST/PUT, 5-source scan
|   |   +-- intros.py        Generate/GET/PUT intro packages
|   |   +-- activity.py      GET activity feed with filters
|   |
|   +-- services/
|       +-- claude_ai.py     Profiling, scoring, intro gen
|       +-- gmail_scan.py    Stub (needs OAuth)
|       +-- hubspot_scan.py  Stub (needs API key)
|       +-- calendar_scan.py Stub (needs OAuth)
|       +-- apollo_enrich.py Stub (needs API key)
|
+-- static/
|   +-- index.html           Dashboard SPA shell
|   +-- app.js               Alpine.js app logic
|
+-- data/
|   +-- pipeline.db          SQLite database
|
+-- .env                     API keys (not committed)
+-- .env.example             Key template
+-- requirements.txt         Python dependencies
+-- run.sh                   One-command startup
```

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | /api/clients | List all clients |
| POST | /api/clients | Create client |
| GET | /api/clients/{id}/criteria | List scoring criteria |
| POST | /api/clients/{id}/criteria | Add criterion |
| GET | /api/prospects | List/search prospects |
| POST | /api/prospects/bulk | Create from name list |
| POST | /api/prospects/import-csv | Upload CSV |
| GET | /api/pipeline/{client_id} | Ranked pipeline with filters |
| POST | /api/pipeline/quick-add | Add single company by name |
| DELETE | /api/pipeline/{entry_id} | Remove from pipeline |
| POST | /api/pipeline/{id}/score | Score single entry |
| POST | /api/pipeline/{client_id}/score-all | Score entire pipeline |
| PUT | /api/pipeline/{client_id}/weights | Change PMF/RS weights |
| GET | /api/pipeline/{client_id}/export | CSV download |
| GET | /api/pipeline/{client_id}/summary | Tier counts + averages |
| GET | /api/relationships/{prospect_id} | Contacts for a prospect |
| POST | /api/relationships | Add/update relationship |
| POST | /api/relationships/{id}/scan | Run 5-source scan |
| POST | /api/intros/generate/{entry_id} | Generate intro package |
| GET | /api/intros/{entry_id} | Get existing package |
| PUT | /api/intros/{id} | Update/mark sent |
| GET | /api/activity | Activity feed |

## Extending the System

**Add a new data source for relationship scanning:**
1. Create `app/services/new_source.py` returning `{hits: int, details: list}`
2. Add columns to `relationship_scans` model (`new_source_hits`, `new_source_details`)
3. Wire into the scan sequence in `routers/relationships.py`

**Add a new client:**
1. Create client via API or seed
2. Generate custom scoring criteria (4-6 per client)
3. Same pipeline of prospects can be re-scored with different criteria

**Add a new ecosystem:**
Upload any CSV with Partner Name/Type/Region/Tier columns via `/api/prospects/import-csv`

## Seed Data (Loaded on First Run)

| Data | Count | Source |
|------|-------|--------|
| Tivly client profile | 1 | company_profile_template.md |
| Scoring criteria | 4 | Build spec |
| Scott Montgomery companies | 16 | Email March 27, 2026 |
| Guidewire ecosystem | 30 | guidewire_ecosystem.csv |
| Known relationships | 6 | relationship_map.md |
| Conference attendees | 5 | AIR 2025 (known entries) |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9, FastAPI, SQLAlchemy |
| Database | SQLite |
| Frontend | HTML, Tailwind CSS (CDN), Alpine.js (CDN) |
| AI | Anthropic Claude API (claude-sonnet-4-20250514) |
| Server | Uvicorn |
