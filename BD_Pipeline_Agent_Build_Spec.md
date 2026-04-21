# BD Pipeline Agent: Build Spec for Claude Code
## Technical Specification v1.0

**Author:** Vinnie Garth, Vinsational Consulting
**Date:** April 17, 2026
**Purpose:** Hand this document to Claude Code. It contains everything needed to build a fully functional BD Pipeline Agent as a standalone web application.

---

## What This Is

A business development pipeline management tool that takes a list of prospect companies, runs a relationship and fit analysis across multiple data sources, scores and ranks them, and generates ready-to-send introduction packages. The user (Vinnie) works as a connector/reseller introducing his clients' products to prospect companies using his personal network.

## What It Needs to Do

### The Core Loop

1. **Client** sends Vinnie a list of target companies (via email, call, or paste)
2. **Agent ingests** the list and associates it with that client
3. **Agent scans** five data sources for existing relationships at each company
4. **Agent scores** each company for product-market fit with the client
5. **Agent calculates** a Matchmaker Score combining fit + relationship strength
6. **Agent ranks** the pipeline by score and assigns action tiers (Hot/Warm/Monitor/Pass)
7. **Vinnie reviews** the ranked list and selects companies to pursue
8. **Agent generates** word-for-word introduction emails and talking points
9. **Vinnie sends** intros, updates relationship scores as conversations happen
10. **Agent recalculates** and resurfaces new opportunities

This loop runs continuously. New companies get added. Relationships change. Scores shift. The agent tracks all of it.

---

## Architecture

### Stack Recommendation

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | React + Tailwind CSS | Dashboard UI, interactive scoring panels |
| Backend | Node.js or Python (FastAPI) | API endpoints, scoring logic, integration orchestration |
| Database | SQLite (start) or PostgreSQL (scale) | Persistent state for companies, scores, relationships, clients |
| AI Layer | Anthropic Claude API (claude-sonnet-4-20250514) | Company research, scoring reasoning, intro email generation, email parsing |
| Integrations | Gmail API, Google Calendar API, HubSpot API, Apollo.io API | Five-source relationship scanning |

### Why Not Just Claude Chat

The current process works in Claude.ai but has these limitations:
- No persistent state between conversations
- Can't run on a schedule
- Can't track score changes over time
- No visual dashboard
- Every session requires re-loading context
- Can't be shared with a client or teammate

---

## Data Model

### Tables

#### clients
```sql
CREATE TABLE clients (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,                    -- "Tivly", "Circle AI", etc.
  website TEXT,
  description TEXT,                      -- What the client does (1-2 sentences)
  primary_revenue_driver TEXT,           -- Their main product/service
  target_buyer TEXT,                     -- Who they sell to
  profile_json TEXT,                     -- Full company profile (JSON blob)
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

#### scoring_criteria
```sql
CREATE TABLE scoring_criteria (
  id INTEGER PRIMARY KEY,
  client_id INTEGER REFERENCES clients(id),
  name TEXT NOT NULL,                    -- "Distribution Alignment"
  description TEXT,                      -- What it measures
  why_it_matters TEXT,                   -- Connection to client value prop
  weight INTEGER DEFAULT 5,             -- 1-10 importance weight
  sort_order INTEGER,                   -- Display order
  created_at TIMESTAMP DEFAULT NOW()
);
```

#### prospects
```sql
CREATE TABLE prospects (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,                    -- "Sentry Insurance"
  type TEXT,                             -- "Regional Carrier", "National Brokerage", etc.
  website TEXT,
  domain TEXT,                           -- "sentry.com" (for email matching)
  alternate_domains TEXT,                -- JSON array of alternate domains
  hq_city TEXT,
  hq_state TEXT,
  employees INTEGER,
  revenue TEXT,
  description TEXT,                      -- What they do (from enrichment)
  decision_makers_json TEXT,             -- JSON array of {name, title, email, source}
  enrichment_source TEXT,                -- "apollo", "web", "hubspot"
  enrichment_date TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

#### pipeline_entries
```sql
CREATE TABLE pipeline_entries (
  id INTEGER PRIMARY KEY,
  client_id INTEGER REFERENCES clients(id),
  prospect_id INTEGER REFERENCES prospects(id),
  source TEXT,                           -- "Scott Montgomery email 3/27/2026"
  source_date DATE,
  source_priority TEXT,                  -- "first-mentioned", "standard"
  tier TEXT DEFAULT 'unscored',          -- "hot", "warm", "monitor", "pass", "unscored"
  pmf_score REAL,                        -- 0-100
  relationship_score INTEGER DEFAULT 0,  -- 0-5
  matchmaker_score REAL,                 -- 0-100 (calculated)
  pmf_weight REAL DEFAULT 0.6,
  rs_weight REAL DEFAULT 0.4,
  status TEXT DEFAULT 'new',             -- "new", "scored", "outreach_sent", "meeting_set", "intro_made", "closed"
  next_action TEXT,
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(client_id, prospect_id)
);
```

#### criterion_scores
```sql
CREATE TABLE criterion_scores (
  id INTEGER PRIMARY KEY,
  pipeline_entry_id INTEGER REFERENCES pipeline_entries(id),
  criterion_id INTEGER REFERENCES scoring_criteria(id),
  score INTEGER DEFAULT 0,              -- 0-5
  reasoning TEXT,                        -- Why this score (AI-generated)
  created_at TIMESTAMP DEFAULT NOW()
);
```

#### relationships
```sql
CREATE TABLE relationships (
  id INTEGER PRIMARY KEY,
  prospect_id INTEGER REFERENCES prospects(id),
  contact_name TEXT,
  contact_title TEXT,
  contact_email TEXT,
  contact_linkedin TEXT,
  score INTEGER DEFAULT 0,              -- 0-5 (relationship strength)
  context TEXT,                          -- How Vinnie knows them
  source TEXT,                           -- "gmail", "hubspot", "calendar", "conference", "manual"
  last_touch DATE,
  warmest_path TEXT,                     -- "Direct", "Via Richard Learey", "AIR 2025 co-attendee"
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

#### relationship_scans
```sql
CREATE TABLE relationship_scans (
  id INTEGER PRIMARY KEY,
  prospect_id INTEGER REFERENCES prospects(id),
  scan_date TIMESTAMP DEFAULT NOW(),
  gmail_hits INTEGER DEFAULT 0,
  gmail_details TEXT,                    -- JSON: [{contact, subject, date, snippet}]
  hubspot_hits INTEGER DEFAULT 0,
  hubspot_details TEXT,                  -- JSON: [{contact_id, name, title, email}]
  calendar_hits INTEGER DEFAULT 0,
  calendar_details TEXT,                 -- JSON: [{event_name, date, attendees}]
  conference_hits INTEGER DEFAULT 0,
  conference_details TEXT,               -- JSON: [{attendee_name, title, conference_name}]
  relationship_map_hits INTEGER DEFAULT 0,
  relationship_map_details TEXT,
  final_rs INTEGER,                      -- Calculated RS after all sources
  evidence_summary TEXT                  -- Human-readable summary of evidence
);
```

#### intro_packages
```sql
CREATE TABLE intro_packages (
  id INTEGER PRIMARY KEY,
  pipeline_entry_id INTEGER REFERENCES pipeline_entries(id),
  target_contact TEXT,                   -- Who the email is addressed to
  target_title TEXT,
  email_subject TEXT,
  email_body TEXT,                       -- Word-for-word outreach email
  talking_points TEXT,                   -- JSON array
  value_prop_prospect TEXT,              -- Why this helps the prospect
  value_prop_client TEXT,                -- Why this helps the client
  mutual_connections TEXT,               -- JSON array
  objections_json TEXT,                  -- JSON array of {objection, response}
  status TEXT DEFAULT 'draft',           -- "draft", "approved", "sent"
  sent_date TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);
```

#### activity_log
```sql
CREATE TABLE activity_log (
  id INTEGER PRIMARY KEY,
  pipeline_entry_id INTEGER,
  action TEXT,                           -- "scored", "relationship_updated", "intro_sent", "meeting_set", "tier_changed"
  old_value TEXT,
  new_value TEXT,
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
```

#### conference_attendees
```sql
CREATE TABLE conference_attendees (
  id INTEGER PRIMARY KEY,
  conference_name TEXT,                  -- "AIR 2025"
  conference_date TEXT,
  attendee_name TEXT,
  title TEXT,
  company TEXT,
  city TEXT,
  state TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
```

---

## API Integrations

### 1. Gmail API
**Purpose:** Search for email history with prospect companies
**Scopes needed:** `gmail.readonly`
**Key operations:**
- Search threads by domain: `from:@{domain} OR to:@{domain}`
- Search threads by company name: `"{company name}"`
- Get full thread content for context extraction
**Filtering:** Exclude automated emails (noreply@, password resets, marketing blasts). Only count genuine human correspondence.

### 2. Google Calendar API
**Purpose:** Find past meetings and shared event attendance
**Scopes needed:** `calendar.readonly`
**Key operations:**
- Search events by company name: `fullText="{company name}"`
- Search over a 2-year lookback window
- Extract attendee lists and check for prospect domain matches

### 3. HubSpot API
**Purpose:** Check CRM for existing contacts and company records
**Key operations:**
- Search contacts by company name
- Search companies by name
- Pull contact properties: name, title, email, company, last activity
**Note:** Use HubSpot's search API, not list all. Filter by the prospect company name.

### 4. Apollo.io API
**Purpose:** Firmographic enrichment (company data)
**Key operations:**
- Bulk org enrichment (up to 10 per call, works on free plan)
- Pull: description, revenue, employee count, HQ, industry, LinkedIn
**Limitation:** People Search requires paid plan. For contact-level data, fall back to web search or LinkedIn.

### 5. Anthropic Claude API
**Purpose:** AI-powered scoring, research, and content generation
**Model:** claude-sonnet-4-20250514
**Key operations:**
- Company profiling (research a prospect, generate structured profile)
- Scoring reasoning (given a company profile and scoring criteria, output 0-5 scores with reasoning)
- Intro email generation (given prospect profile + client profile + relationship context, generate outreach email)
- Email parsing (extract company names from email thread content)

---

## Scoring Engine

### Product-Market Fit (PMF) Calculation

```
For each prospect:
  raw_pmf = 0
  max_possible = 0
  
  For each criterion:
    raw_pmf += (criterion_score / 5) * criterion_weight
    max_possible += criterion_weight
  
  normalized_pmf = (raw_pmf / max_possible) * 100
```

### Relationship Strength (RS) Scale

| Score | Label | Evidence |
|-------|-------|----------|
| 5 | Inner Circle | Former employer, active business partner, done deals together |
| 4 | Strong | Multiple email threads, past meetings, active collaboration |
| 3 | Warm | Met at conference, occasional emails, mutual connections vouch |
| 2 | Light | LinkedIn connection, one email thread, one-hop intro available |
| 1 | Aware | Name appears in shared event list or CRM, no direct contact |
| 0 | Cold | Zero hits across all five sources |

### Matchmaker Score

```
matchmaker_score = (normalized_pmf * pmf_weight) + ((rs / 5 * 100) * rs_weight)
```

Default weights: pmf_weight = 0.6, rs_weight = 0.4

User can adjust per pipeline or globally.

### Tier Assignment

| Score Range | Tier | Default Action |
|-------------|------|---------------|
| 70+ | Hot | Priority outreach. Generate intro package. |
| 50-69 | Warm | Secondary outreach. Worth an intro if relationship exists. |
| 30-49 | Monitor | Track for changes. Not worth spending capital yet. |
| Below 30 | Pass | Skip unless something changes. |

---

## Five-Source Relationship Scan

This is the core differentiator. For each prospect company, the agent checks five data sources in sequence and compiles the evidence.

### Scan Sequence

```
function scanRelationship(prospect) {
  results = {gmail: [], hubspot: [], calendar: [], conference: [], relmap: []}
  
  // 1. Gmail
  // Search: from/to @{prospect.domain} AND @{prospect.alternate_domains}
  // Search: "{prospect.name}" as text search
  // Filter out: noreply, password resets, marketing, system notifications
  // Extract: contact name, title if available, subject line, date, thread nature
  
  // 2. HubSpot
  // Search contacts where company matches prospect name
  // Search companies by name
  // Extract: contact records with name, title, email, last activity
  
  // 3. Google Calendar
  // Search events with fullText=prospect.name, last 2 years
  // Check attendee lists for prospect domain
  // Extract: event name, date, co-attendees
  
  // 4. Conference Attendees
  // Query conference_attendees table where company matches prospect name
  // Extract: attendee name, title, conference name
  
  // 5. Relationship Map
  // Query relationships table for this prospect
  // Extract: existing contacts, scores, context
  
  // Calculate RS
  rs = calculateRS(results)
  
  // Generate evidence summary
  evidence = generateEvidenceSummary(results)
  
  return {score: rs, evidence: evidence, contacts: extractBestContacts(results)}
}
```

### RS Calculation Logic

```
function calculateRS(results) {
  // Start at 0, build up based on evidence
  
  if (results has former employer evidence) return 5
  if (results has multiple email threads + meetings) return 4
  if (results has conference attendee + at least one email) return 3
  if (results has one email thread OR hubspot contact OR linkedin connection) return 2
  if (results has conference attendee only OR CRM record with no activity) return 1
  if (results has zero hits across all sources) return 0
  
  // Note: this is simplified. The AI layer should evaluate the actual
  // evidence and make a judgment call. Use Claude to assess the evidence
  // and assign the score with reasoning.
}
```

---

## Dashboard UI

### Views

#### 1. Pipeline Overview (Default View)
- Dropdown: Select active client (Tivly, Circle AI, etc.)
- Dropdown: Scoring weight preset (Default 60/40, Cold Prospecting 80/20, Network First 30/70)
- Summary cards: Total companies, Hot count, Warm count, Monitor count, Pass count
- Main table: Ranked pipeline with columns:
  - Rank
  - Company Name (clickable to expand detail panel)
  - Type (carrier, brokerage, wholesale)
  - PMF Score (color bar)
  - RS Score (dot visualization, 5 dots)
  - Matchmaker Score (bold number)
  - Tier (color badge: green/yellow/gray/red)
  - Best Contact
  - Status (new, scored, outreach sent, meeting set, intro made)
  - Next Action
- Filters: Tier, Type, RS range, PMF range, Status
- Sort: By Matchmaker Score (default), by PMF, by RS, by name
- Bulk actions: Score selected, Generate intros for selected, Export CSV

#### 2. Company Detail Panel (Slide-out or Modal)
- Company profile (name, type, HQ, employees, revenue, description)
- Relationship scan results (all five sources with evidence)
- Scoring breakdown (each criterion with score, weight, reasoning)
- Contact list (all known contacts with source and last touch)
- Activity timeline (every score change, email, meeting, status update)
- Intro package (if generated, with email preview)
- Actions: Edit scores, Update RS, Generate intro, Mark status

#### 3. Relationship Map View
- Visual network showing Vinnie's connections across all prospect companies
- Node size = relationship strength
- Edge color = client fit (which client they're being evaluated for)
- Cluster by: Company type, Tier, Conference, or Network multiplier
- Highlight: warming opportunities (high PMF, low RS)

#### 4. Intro Package Generator
- Select a company from the pipeline
- Pre-filled with: best contact, client profile, relationship context
- Preview the generated email
- Edit before sending
- Track: sent date, response received, meeting set

#### 5. Activity Feed
- Chronological log of all pipeline changes
- Filterable by client, company, action type
- Shows: score changes, new companies added, intros sent, meetings set, tier promotions

#### 6. Conference Cross-Reference
- Upload attendee list (CSV or PDF)
- Auto-match against active pipeline companies
- Surface new contacts at target companies
- Suggest relationship score updates

---

## AI Prompts (Claude API Calls)

### Prompt 1: Company Profiling
```
System: You are a B2B business development analyst. Research the following company 
and produce a structured profile.

User: Profile {company_name}. I need: what they sell, who they sell to, how they 
go to market, problems they solve, their value chain position, and 3-5 competitors. 
Format as JSON matching this schema: {profile_schema}
```

### Prompt 2: Scoring
```
System: You are scoring prospect companies for product-market fit with a specific client.

User: Score {prospect_name} against these criteria for {client_name}:
{criteria_list}

Client profile: {client_profile}
Prospect profile: {prospect_profile}

For each criterion, provide a score (0-5) and a one-sentence reasoning.
Format as JSON: [{criterion_id, score, reasoning}]
```

### Prompt 3: Intro Email Generation
```
System: You are writing a business introduction email. The sender (Vinnie) is 
introducing his client's product/service to a prospect company. Write in 
Vinnie's voice: direct, conversational, confident, no corporate jargon. 
No em dashes. No buzzwords (passionate, leveraged, architected, seamless, 
scalable, dynamic). Short paragraphs. Include a specific stat about the client. 
End with a clear ask.

User: Write an introduction email.
From: Vinnie Garth
To: {contact_name}, {contact_title} at {prospect_company}
Introducing: {client_name} ({client_one_liner})
Key stat: {client_key_stat}
Relationship context: {how_vinnie_knows_contact}
Why this is a fit: {fit_reasoning}
```

### Prompt 4: Email Thread Parsing
```
System: Extract company names from this email thread. The sender is asking the 
recipient to make introductions to specific companies. Return ONLY the company 
names as a JSON array. Do not include the sender's company or the recipient's 
company.

User: {email_thread_content}
```

### Prompt 5: Relationship Evidence Assessment
```
System: Based on the following evidence from five data sources, assign a 
relationship strength score (0-5) and explain your reasoning in one sentence.

Scale:
5 = Inner Circle (former employer, active business partner)
4 = Strong (multiple email threads, past meetings)
3 = Warm (conference meeting, occasional emails)
2 = Light (one email, LinkedIn connection, one-hop intro)
1 = Aware (name in event list, CRM record, no direct contact)
0 = Cold (zero evidence)

User: Evidence for {prospect_name}:
Gmail: {gmail_results}
HubSpot: {hubspot_results}
Calendar: {calendar_results}
Conference: {conference_results}
Relationship Map: {relmap_results}

Return JSON: {score: N, reasoning: "...", best_contact: "...", warmest_path: "..."}
```

---

## User Preferences (Hardcoded)

These are Vinnie's preferences. Apply to all outputs.

### Writing Style
- Direct, conversational, confident
- No em dashes
- No buzzwords: passionate, leveraged, architected, seamless, scalable, dynamic
- Word-for-word email scripts, not talking points
- Short paragraphs (2-3 sentences)
- Bold numbers and stats

### Visual Preferences
- Force light mode (hardcoded hex values, not CSS theme variables)
- Strong visual hierarchy in tables and dashboards
- Color coding: Hot=green, Warm=yellow, Monitor=gray, Pass=red
- Dot visualization for 0-5 scores (filled/unfilled circles)

### Timezone
- America/Chicago (Central Time)

---

## MVP Scope (Build This First)

### Phase 1: Core Pipeline
- [ ] Database setup with all tables
- [ ] Manual company ingestion (paste a list, auto-create prospect records)
- [ ] Five-source relationship scan (Gmail, HubSpot, Calendar API integrations)
- [ ] Conference attendee import (CSV upload, parse into conference_attendees table)
- [ ] Scoring engine (criteria management, PMF calculation, Matchmaker Score)
- [ ] Dashboard: Pipeline Overview with ranked table and filters
- [ ] Dashboard: Company Detail Panel with scan results and scoring breakdown

### Phase 2: AI Layer
- [ ] Claude API integration for company profiling
- [ ] Claude API integration for automated scoring with reasoning
- [ ] Claude API integration for intro email generation
- [ ] Claude API integration for email thread parsing (extract company names)
- [ ] Intro Package Generator view

### Phase 3: Automation
- [ ] Gmail periodic scan (check for new emails from active client contacts)
- [ ] Score change alerts (when a relationship update changes a company's tier)
- [ ] Activity feed with full audit trail
- [ ] CSV export for CRM import
- [ ] Relationship Map visualization

### Phase 4: Multi-Client
- [ ] Client switcher (score same companies for different clients)
- [ ] Per-client scoring criteria management
- [ ] Cross-client opportunity detection ("this company is a fit for both Tivly AND Circle AI")

---

## Existing Data to Seed

The following data already exists and should be imported on first run:

### Tivly Client Profile
Already profiled. See the `company_profile_template.md` in the project files for the full Tivly profile including scoring criteria.

### Tivly Scoring Criteria
| Criterion | Weight | Description |
|-----------|--------|-------------|
| Distribution Alignment | 5 | Works in policy/underwriting/digital distribution vs claims-only |
| SMB Commercial Focus | 5 | Focused on small commercial lines |
| Digital CX / Acquisition | 4 | Improves digital customer journey |
| Lead Gen Compatibility | 5 | Could benefit from or complement Tivly's lead generation |

### Scott Montgomery's 16-Company Pipeline
Grange, Sentry, Amtrust, State Farm, Shelter, Assured Partners, Goosehead, Selective, NatGen, Country Financial, Westfield, Erie, Cincinnati, Guard, CRC, McGriff

Source: Scott Montgomery email, March 27, 2026. Erie and Cincinnati were first-mentioned on March 6, 2026.

### Relationship Data (Already Discovered)
| Company | RS | Best Contact | Source | Evidence |
|---------|-----|-------------|--------|----------|
| Sentry | 5 | Richard Learey (BD, Dairyland) | Gmail, Calendar | Former employer ~20 years. Active email relationship. Made introductions on Vinnie's behalf. |
| Erie | 2 | Cody Cook (EVP Claims) + Danielle Hermann (Dir Agent Mktg) | HubSpot + AIR 2025 | CRM contact + conference attendee. No direct email threads. |
| State Farm | 1 | Brian Tira (Dir Financial Ops) | AIR 2025, shared 2021 dinner | Same industry dinner invite 2021, AIR attendees. Peripheral. |
| Cincinnati | 1 | Scott Kelly (AVP Product Mgmt) | AIR 2025 | Conference attendee only. |
| Country Financial | 1 | Andrew Walter (Mgr PL Data/Analytics) | AIR 2025 | Conference attendee only. PL/data title, not commercial distribution. |

### AIR 2025 Conference Attendees
300+ attendees. PDF already parsed. Import into conference_attendees table.

### Guidewire Ecosystem (Existing Scored Data)
252 partners with Tivly fit scores. CSV exists. Can be imported as a second pipeline for cross-referencing.

---

## File References

These files contain the full context and should be provided to Claude Code alongside this spec:

| File | What It Contains | Import As |
|------|-----------------|-----------|
| `scoring_methodology.md` | Full Matchmaker Score formula, tier weights, criteria generation rules | Reference doc for scoring engine |
| `company_profile_template.md` | Template for company profiling + completed Tivly profile | Seed data for Tivly client |
| `relationship_map.md` | Current relationship entries | Seed data for relationships table |
| `guidewire_ecosystem.csv` | 252 Guidewire partners with Tivly scores | Optional second pipeline |
| `2025_AIR_Conference_Attendees.pdf` | 300+ conference attendees | Seed data for conference_attendees table |
| `Partner_Ecosystem_Scoring_Workflow.md` | Documentation of the original workflow | Reference only |
| `QUICK_START.md` | User-facing command reference | Reference for UI command patterns |
| `BD_Pipeline_Agent_SKILL.md` | The agent skill definition (prompt playbook) | Reference for AI prompt patterns |
| `BD_Pipeline_Agent_COMMANDS.md` | Copy/paste command reference | Reference for UI interaction patterns |

---

## Success Criteria

The agent is working when Vinnie can:

1. Paste a list of 16 companies and see them scored, ranked, and tiered in under 2 minutes
2. Click on any company and see the full five-source relationship scan with evidence
3. Click "Generate Intro" and get a word-for-word email he can copy and send
4. Update a relationship score and watch the pipeline re-rank in real time
5. Switch from Tivly to Circle AI and see the same companies re-scored with different criteria
6. Export a CSV of the ranked pipeline for CRM import
7. Come back tomorrow and everything is still there (persistent state)
8. See an activity feed showing what changed since his last session
