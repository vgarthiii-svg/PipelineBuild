# BD Pipeline Agent — Information Flow Map

Companion to [ARCHITECTURE.md](ARCHITECTURE.md). This document traces the full flow of information through the system and annotates, at each juncture, exactly which sources feed in.

## Legend
- **[LIVE]** = real data source, wired and returning data
- **[STUB]** = placeholder in `app/services/`, returns zeros until API keys added
- **[MANUAL]** = Vinnie enters data through UI or seed files
- **[FILE]** = loaded from a file on disk at startup or on upload

---

## LAYER 1 — INGESTION (what enters the system)

```
                          ┌──────────────────────────────────────┐
                          │  SOURCES FEEDING THE SYSTEM          │
                          └──────────────────────────────────────┘

 [FILE]  company_profile_template.md ──┐
 [FILE]  relationship_map.md ──────────┤
 [FILE]  guidewire_ecosystem.csv ──────┼──► app/seed.py  (first-run only)
 [FILE]  2025_AIR_Conference_          │        │
         Attendees.pdf (parsed) ───────┤        │
 [FILE]  BD_Pipeline_Agent_Build_      │        │
         Spec.md (Tivly criteria) ─────┘        ▼
                                        ┌──────────────────┐
                                        │   SQLite:        │
 [MANUAL]  UI: "Add client" form ──────►│   pipeline.db    │
 [MANUAL]  UI: "Quick add prospect" ───►│                  │
 [MANUAL]  UI: paste list / CSV ───────►│   9 tables       │
 [MANUAL]  UI: add relationship ───────►│                  │
 [MANUAL]  UI: upload CSV ─────────────►└──────────────────┘
              (/api/prospects/import-csv)
```

**Tables populated at this layer:** `clients`, `scoring_criteria`, `prospects`, `relationships`, `conference_attendees`.

---

## LAYER 2 — ENRICHMENT (company profiling)

Triggered when: a prospect is added via quick-add, or user clicks "Profile" in UI.

```
   prospect.name (string)
         │
         ▼
 ┌──────────────────────────────────────────────────┐
 │  app/services/claude_ai.py :: profile_company()  │
 │  Source: [LIVE] Anthropic Claude API             │
 │          model: claude-sonnet-4-20250514         │
 │          key: ANTHROPIC_API_KEY (.env)           │
 └──────────────────────────────────────────────────┘
         │
         ▼
   JSON payload → prospects.profile_json
     { products, target_buyer, go_to_market,
       problems_solved, value_chain_upstream,
       value_chain_downstream, competitors }
```

**No other sources feed this juncture.** Claude's training data is the sole research input — there is no web-search augmentation, no Apollo enrichment (Apollo service is [STUB]).

---

## LAYER 3 — 5-SOURCE RELATIONSHIP SCAN (the core discovery moment)

Triggered when: `POST /api/relationships/{prospect_id}/scan` — called from UI or batch job.

```
  prospect (id, name, domain)
         │
         ├──► Source 1: Gmail        [STUB]  app/services/gmail_scan.py
         │                           Would query: from:@{domain} OR to:@{domain}
         │                           Needs: Google OAuth token
         │                           Currently returns: {hits: 0, details: []}
         │
         ├──► Source 2: HubSpot      [STUB]  app/services/hubspot_scan.py
         │                           Would query: contacts/companies by name
         │                           Needs: HUBSPOT_API_KEY
         │                           Currently returns: {hits: 0, details: []}
         │
         ├──► Source 3: Google Cal   [STUB]  app/services/calendar_scan.py
         │                           Would query: fullText={name}, 2yr window
         │                           Needs: Google OAuth token
         │                           Currently returns: {hits: 0, details: []}
         │
         ├──► Source 4: Conference DB [LIVE] conference_attendees table
         │                           Query: company ILIKE '%{prospect.name}%'
         │                           Seeded from: AIR 2025 PDF (5 entries)
         │                           Returns: attendee_name, title, conf_name
         │
         └──► Source 5: Relationship Map [LIVE] relationships table
                                      Query: prospect_id = {id}
                                      Seeded from: relationship_map.md (6 rows)
                                      Returns: contact, score, context, path
         │
         ▼
 ┌────────────────────────────────────────────────┐
 │  relationships.py :: scan_relationships()      │
 │  Aggregates all 5 into a RelationshipScan row  │
 └────────────────────────────────────────────────┘
         │
         ▼
   relationship_scans table
     { gmail_hits, hubspot_hits, calendar_hits,
       conference_hits, relmap_hits,
       final_rs (0-5), evidence_summary }

   final_rs derivation (see relationships.py:176-181):
     • if any relationship exists → MAX(relationship.score)
     • elif conference hit        → 1
     • else                        → 0
```

**Important:** today the final RS is driven almost entirely by Source 5 (manually-entered relationships). Sources 1–3 contribute nothing until OAuth/keys are wired. Source 4 only bumps RS from 0 → 1.

---

## LAYER 4 — SCORING (two parallel tracks, then merge)

```
   TRACK A: PMF (Product-Market Fit)                TRACK B: RS (Relationship Strength)
   ═══════════════════════════════════              ═══════════════════════════════════

   Inputs fed in:                                   Inputs fed in:
     • prospect.profile_json  (from Layer 2)           • relationships table (Source 5)
     • client.description                              • relationship_scans.final_rs
     • client.target_buyer                               (from Layer 3)
     • scoring_criteria (weight 1-10, per client)
                                                     relationships.py :: _sync_rs_to_pipeline
   claude_ai.py :: score_prospect()                   picks MAX(score) across all rels
   Source: [LIVE] Claude API                          for this prospect
         │                                                  │
         ▼                                                  ▼
   criterion_scores table                            pipeline_entries.relationship_score
     (0-5 per criterion, with                          (integer 0-5)
      written reasoning)
         │
         ▼
   scoring.py :: calculate_pmf()
   PMF = Σ(score/5 * weight) / Σ(weight) * 100
         │
         ▼
   pipeline_entries.pmf_score (0-100)


                    TRACKS MERGE:
                    ═════════════
           scoring.py :: calculate_matchmaker()
           MM = (PMF × W1) + ((RS/5 × 100) × W2)
           Default W1=0.6, W2=0.4 (adjustable per pipeline)
                          │
                          ▼
                    assign_tier()
                    70+ Hot / 50-69 Warm / 30-49 Monitor / <30 Pass
                          │
                          ▼
           pipeline_entries.matchmaker_score + tier
```

---

## LAYER 5 — INTRO PACKAGE GENERATION

Triggered when: user clicks "Generate intro" on a Hot-tier entry. `POST /api/intros/generate/{entry_id}`.

```
   Inputs assembled from DB:
     • client (name, description, target_buyer, profile_json)   ◄── Layer 1/2
     • prospect (name, description, profile_json)               ◄── Layer 1/2
     • best relationship (contact_name, title, warmest_path)    ◄── Layer 3 / manual
     • top scoring criteria + reasoning                         ◄── Layer 4
         │
         ▼
 ┌────────────────────────────────────────────────────┐
 │  claude_ai.py :: generate_intro_package()          │
 │  Source: [LIVE] Claude API                         │
 │  Style guide hardcoded: Vinnie's voice rules       │
 │    (no em dashes, no corporate filler, etc.)       │
 └────────────────────────────────────────────────────┘
         │
         ▼
   intro_packages table
     { target_contact, email_subject, email_body,
       talking_points, value_props, objections_json }
```

---

## LAYER 6 — AUDIT / ACTIVITY (write-only, fed by every mutation)

```
  Feeders (every state change writes here):
     • clients.py        — client/criteria changes
     • prospects.py      — prospect added/updated
     • pipeline.py       — score changes, tier shifts, weight changes
     • relationships.py  — RS updates (see _sync_rs_to_pipeline)
     • intros.py         — intro generated / marked sent
                        │
                        ▼
                activity_log table
                  { action, old_value, new_value,
                    notes, created_at, pipeline_entry_id }
```

---

## LAYER 7 — OUTPUT SURFACES (what the user consumes)

```
                    SQLite pipeline.db
                          │
                          ▼
               FastAPI routers (JSON)
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
   Dashboard SPA    CSV Export     Activity Feed
   static/app.js    /api/pipeline  /api/activity
   (Alpine.js)      /{id}/export
   Tailwind CSS
   http://localhost:8000
```

---

## Weak Points / Thin Sources

1. **Layer 3 is the weakest link.** 3 of 5 sources are stubs. Until Gmail/HubSpot/Calendar are wired, RS is driven by what you already knew you had.
2. **Layer 2 has no web grounding.** Claude profiles companies from memory; no Apollo, no web search. Data can be stale or hallucinated.
3. **No feedback loop from Layer 5 back into scoring.** Intros sent don't influence future RS unless you manually update a relationship row.
4. **Seed data is the original source of truth** for the first ~58 rows in the system (see ARCHITECTURE.md seed-data table).
