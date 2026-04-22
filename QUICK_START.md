# BD Matchmaker: Quick Start
## Setup + Daily Commands

---

## Project Setup (5 min)

1. Create a Claude Project named **BD Matchmaker**
2. Paste SYSTEM_INSTRUCTIONS.md contents into the Project custom instructions
3. Upload these files to the Project knowledge base:
   - `company_profile_template.md`
   - `scoring_methodology.md`
   - `relationship_map.md`
   - `guidewire_ecosystem.csv` (first ecosystem)
   - `2025_AIR_Conference_Attendees.pdf` (prospecting source)
   - This file (`QUICK_START.md`)

---

## The Core Loop

### 1. Profile a company
> "Profile Tivly"

Claude researches the company via web search, Apollo, and HubSpot. Outputs a structured model: products, ICP, value chain, decision makers. This works for ANY company.

### 2. Generate scoring criteria
> "Generate scoring criteria for Tivly"

Claude reads the company profile and auto-generates 4-6 custom criteria. Reviews them with you before proceeding. Criteria are unique to each company.

### 3. Score an ecosystem
> "Score the Guidewire ecosystem for Tivly"

Claude scores every partner against the custom criteria, layers in your relationship strength from the relationship map, and outputs a ranked list with Matchmaker Scores.

### 4. Get the top matches
> "Show me the top 20 with intro angles and decision makers"

Claude gives you ranked matches with rationale, word-for-word outreach angles, and decision maker intel.

---

## Swapping Companies

The system is company-agnostic. To score for a different company:

> "Profile Circle AI"
> "Generate scoring criteria for Circle AI"  
> "Score the Guidewire ecosystem for Circle AI"

New criteria are generated from Circle AI's profile. Same ecosystem, completely different ranking.

---

## Adding a New Ecosystem

> "Scrape the Duck Creek marketplace for partners"

Or upload a CSV with columns: Partner Name, Partner Type, Region, Tier

> "Score the Duck Creek ecosystem for Tivly"

---

## Relationship Map Commands

**Add a contact:**
> "I just met Trae Jones at Appulate. He's their new President. Met him at a conference. Add as a 3."

**Review warming opportunities:**
> "Which of my top 20 Tivly matches have the shortest path to a warm intro?"

**Cross-reference conference attendees:**
> "Check the AIR 2025 attendee list against my top Tivly matches. Who's on both lists?"

---

## Adjusting the Score

**Change the fit/relationship weighting:**
> "Reweight to 80/20 fit over relationship" (cold prospecting)
> "Reweight to 50/50" (maximize network)
> "Reweight to 30/70 relationship first" (post-conference follow-up mode)

**Adjust individual criteria weights:**
> "Increase the weight on SMB Commercial Focus to 8 and drop Digital CX to 3"

**Add or remove a criterion:**
> "Add a criterion for API readiness scored 0-5"
> "Drop the company size modifier"

---

## Prep for an Introduction

> "Prep me for introducing Tivly to Bindable"

Outputs:
1. Word-for-word outreach email
2. 3 talking points for the call
3. The value prop angle for both sides
4. Mutual connections that could warm it up
5. Potential objections and responses

---

## Maintenance

**After every conference/event:** Spend 2 min updating the relationship map. The compounding effect over 90 days is massive.

**After every outreach:** Update the relationship score. A cold 0 that responded becomes a 2. A meeting bumps to 3. A deal bumps to 4-5.

**Monthly:** Re-run the top ecosystem scores. New enrichment data, updated relationships, and criteria refinements will resurface opportunities you missed.
