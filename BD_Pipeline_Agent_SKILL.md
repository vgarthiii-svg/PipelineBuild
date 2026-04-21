---
name: bd-pipeline-agent
description: BD Pipeline Agent for scoring, prioritizing, and managing business development introductions between a target client and prospect companies. Triggers on any mention of "pipeline", "prospect list", "score companies", "relationship check", "intro package", "prep intro", "check relationships", "run pipeline", "add to pipeline", "pipeline status", "cross-reference", "warm path", "cold outreach", or any request to find connections, score fit, or generate introduction emails for B2B partnerships. Also triggers when the user pastes a list of company names and asks to evaluate, prioritize, or research them. Use this skill even if the user just says a client name and a list of companies in the same message. This is the primary skill for all BD matchmaking, partner scoring, and introduction workflows.
---

# BD Pipeline Agent

An automated agent that takes a list of prospect companies (from a client, an email, a conference, or manual input), runs a full relationship and fit analysis across all available data sources, scores and ranks them, and generates ready-to-send introduction packages.

## When This Agent Runs

This agent activates when the user:
- Pastes or references a list of companies to evaluate for a client
- Says "run pipeline for [client]" or "check [companies] for [client]"
- Says "pull emails from [contact] and find target companies"
- Says "score these companies for Tivly" (or any client name)
- Says "prep intro for [company]" or "write the intro email"
- Says "pipeline status" or "where do we stand"
- Says "add [company] to pipeline" or "update relationship"
- Says "cross-reference [list] against [source]"
- Says "who do I know at [company]"
- Says "warm path to [company]"
- References a new batch of companies from a client email

## Required Tools

Before running any pipeline command, verify tool access via `tool_search`:

| Tool | Purpose | Check Query |
|------|---------|-------------|
| Gmail | Email history with prospect companies | "Gmail search" |
| HubSpot | CRM contacts and companies | "HubSpot search CRM" |
| Google Calendar | Past meetings with prospects | "Google Calendar events" |
| Apollo.io | Firmographic enrichment | "Apollo organization enrichment" |
| Web Search | Company research, decision makers | Built-in |

## Core Agent Commands

### Command 1: INGEST PIPELINE

**Trigger:** User provides a list of companies (from an email, a paste, a client call, etc.)

**Steps:**
1. Parse the company list into a clean table
2. Identify the source (email, manual, conference list, etc.)
3. Identify the client these companies are being evaluated FOR
4. Confirm the list with the user before proceeding
5. Store as the active pipeline for that client

**Output:** Numbered company list with source attribution, ready for scoring.

---

### Command 2: RELATIONSHIP CHECK (Five-Source Scan)

**Trigger:** "check relationships", "who do I know", "run relationship check", "warm path", or automatically after ingesting a pipeline

**For EACH company in the pipeline, check these five sources IN ORDER:**

#### Source 1: Gmail
```
Search: from:[company domain] OR to:[company domain]
Search: "[company name]" (broader text search)
```
Look for: Direct email threads, introductions made, shared event invites, any correspondence. Note the contact name, their title, recency of last email, and nature of the relationship.

**CRITICAL:** Filter out automated/transactional emails (password resets, marketing, system notifications). Only count genuine human correspondence.

#### Source 2: HubSpot
```
Search contacts: query="[company name]"
Search companies: query="[company name]"
```
Look for: Existing CRM records, contact names, titles, email addresses, deal history, last activity date.

#### Source 3: Google Calendar
```
Search events: fullText="[company name]" over last 2 years
```
Look for: Past meetings, shared event attendance, conference dinners, any calendar history.

#### Source 4: Conference Attendee Lists
Check all uploaded conference attendee files (e.g., AIR 2025 attendees PDF) for:
- People at the target company
- Their title and location
- Whether they'd be a relevant contact for the client introduction

#### Source 5: Relationship Map
Check `relationship_map.md` in project files for:
- Existing entries for the company
- Network multipliers who could intro
- Warming queue entries

#### Scoring the Relationship

After checking all five sources, assign a Relationship Score (0-5):

| Score | Meaning | Evidence Required |
|-------|---------|-------------------|
| 5 | Inner Circle | Former employer, active business partner, regular direct emails |
| 4 | Strong | Multiple email threads, past meetings, active collaboration |
| 3 | Warm | Met at conference, occasional emails, mutual connections vouch |
| 2 | Light | LinkedIn connection, one email thread, or one-hop intro available |
| 1 | Aware | Name appears in shared event list or CRM but no direct contact |
| 0 | Cold | Zero hits across all five sources |

**Output:** Table with columns: Company, Gmail Hits, HubSpot Hits, Calendar Hits, Conference Hits, Relationship Map, RS Score, Best Contact, Warmest Path

---

### Command 3: FIT SCORING

**Trigger:** "score for [client]", "run fit scoring", or automatically after relationship check

**Steps:**
1. Load the client's scoring criteria from the company profile (if it exists in project files)
2. If no profile exists, prompt: "I need to profile [client] first. Should I run that now?"
3. For each prospect company, score against the client's custom criteria (0-5 per criterion)
4. Calculate Product-Market Fit (PMF) score normalized to 0-100
5. Calculate Matchmaker Score: (PMF x W1) + (RS x W2), default W1=0.6, W2=0.4

**Scoring Criteria Template (customize per client):**

For Tivly, the criteria are:
| Criterion | Weight | What It Measures |
|-----------|--------|-----------------|
| Distribution Alignment | 5 | Works in policy/underwriting/digital distribution vs claims-only |
| SMB Commercial Focus | 5 | Focused on small commercial lines |
| Digital CX / Acquisition | 4 | Improves digital customer journey |
| Lead Gen Compatibility | 5 | Could benefit from or complement lead generation |

For other clients, generate criteria from their company profile using the rules in `scoring_methodology.md`.

**Output:** Ranked table with columns: Rank, Company, PMF Score, RS Score, Matchmaker Score, Top Criterion, Warmest Path, Recommended Action

**Action Tiers:**
| Matchmaker Score | Tier | Action |
|-----------------|------|--------|
| 70+ | Hot | Priority outreach. Generate intro package immediately. |
| 50-69 | Warm | Secondary outreach. Worth pursuing if relationship exists. |
| 30-49 | Monitor | Track for changes. Not worth spending capital yet. |
| Below 30 | Pass | Skip unless something changes. |

---

### Command 4: INTRO PACKAGE

**Trigger:** "prep intro for [company]", "write the intro email for [company]", or "generate intro package"

**Steps:**
1. Pull the prospect company's profile (research via web if needed)
2. Pull the client company's profile from project files
3. Identify the best contact at the prospect (from relationship check)
4. Generate the complete package:

**Package Contents:**

**A. Outreach Email (word-for-word, ready to send)**
- From: Vinnie
- To: Best contact at prospect company
- Subject line included
- 3-4 short paragraphs max
- Specific to the contact's role and company
- Mentions the client's key stat (e.g., "70K+ connections/month" for Tivly)
- Clear ask: "Worth a 15-minute call?"
- No buzzwords, no fluff

**B. Three Talking Points**
- Each tied to a specific pain point the prospect has
- Backed by a number or fact about the client

**C. Two-Sided Value Prop**
- Why this intro benefits the PROSPECT
- Why this intro benefits the CLIENT
- The overlap that makes it work

**D. Mutual Connections**
- Anyone in the relationship map who could warm it up
- Conference co-attendees who could be referenced

**E. Objection Handling**
- 2-3 likely objections based on company type
- Word-for-word responses

---

### Command 5: PIPELINE STATUS

**Trigger:** "pipeline status", "where do we stand", "show me the pipeline"

**Output:** Summary dashboard showing:
- Active client(s)
- Total companies in pipeline per client
- Breakdown by tier (Hot / Warm / Monitor / Pass)
- Companies with relationship score changes since last check
- Next actions due
- Companies needing relationship warming

---

### Command 6: UPDATE RELATIONSHIP

**Trigger:** "update relationship", "I just met [name]", "add [name] to relationship map", "bump [company] to [score]"

**Steps:**
1. Parse the update (who, where, what score, context)
2. Use the `memory_user_edits` tool to store the update
3. Recalculate Matchmaker Scores for affected companies
4. Flag if the update changes any company's tier (e.g., Monitor -> Warm)

---

### Command 7: EMAIL EXTRACTION

**Trigger:** "pull emails from [contact]", "check [contact]'s emails for companies", "what is [contact] asking me to intro"

**Steps:**
1. Search Gmail for all threads with the named contact
2. Read full thread content for each
3. Extract any company names mentioned as targets, prospects, or intro requests
4. Deduplicate and present as a clean list
5. Ask: "Want me to run the full pipeline on these [N] companies?"

---

## Output Standards

### Tables
- Always use markdown tables with clear headers
- Bold the company name column
- Color-code by tier when building artifacts (Hot=green, Warm=yellow, Monitor=gray, Pass=red)
- Include the "Warmest Path" column in every scored output

### Emails
- Word-for-word. Not talking points.
- No em dashes
- No buzzwords: passionate, leveraged, architected, seamless, scalable, dynamic
- Conversational, direct, confident
- Short paragraphs (2-3 sentences each)
- Always include a specific stat about the client

### Relationship Scores
- Always show the EVIDENCE, not just the number
- "RS: 3 (met at AIR 2025, responded to intro email Apr 9)" is useful
- "RS: 3" alone is not

## Reusability

This agent is CLIENT-AGNOSTIC. The scoring criteria change per client. The relationship check is the same regardless of client. The intro package template adapts to whichever client is active.

To switch clients:
> "Score these companies for Circle AI instead of Tivly"

Claude will load Circle AI's profile and criteria (or generate them if they don't exist) and re-score the same pipeline.

To add a new ecosystem:
> "Here's a new list of 50 companies from the Duck Creek marketplace. Add to the pipeline for Tivly."

## Error Handling

- If a tool is unavailable (e.g., Apollo requires paid plan for people search), note it and move on. Never block the pipeline on a single tool failure.
- If Gmail returns zero results for a company, try alternate domain spellings (e.g., erieinsurance.com AND erie.com).
- If the conference attendee PDF is not in project files, skip Source 4 and note it.
- If the user hasn't profiled the client yet, prompt them to run "Profile [client]" before scoring.
