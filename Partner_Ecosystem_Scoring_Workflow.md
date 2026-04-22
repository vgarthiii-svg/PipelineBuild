# Partner Ecosystem Scoring Workflow
## A Reusable AI-Powered BD Prospecting System

**Created by:** Vinnie Garth, Vinsational Consulting
**Use case:** Identifying, scoring, and prioritizing partners from any technology marketplace for business development outreach
**First deployed on:** Guidewire Marketplace (252 partners) for Tivly reseller prospecting

---

## What This Workflow Does

Takes a raw partner ecosystem (hundreds of companies with minimal data) and turns it into a scored, prioritized, enriched prospecting list with custom scoring criteria matched to a specific product or service you're selling into that ecosystem.

**The output:** An interactive scoring panel where you adjust weights with sliders and the entire list re-ranks in real time. Plus a downloadable spreadsheet for CRM import.

**Time to execute:** 30-45 minutes for the full workflow (vs. days of manual research)

---

## The 6-Step Process

### Step 1: Harvest the Partner List

**What you're doing:** Scraping or extracting the full partner directory from the target ecosystem.

**How it was done (Guidewire example):**
- Connected Claude to Chrome via the Claude in Chrome extension
- Navigated to the marketplace URL
- Used JavaScript execution to extract partner names, types, regions, and tiers
- Paginated through all results (set to 100 per page, captured 3 pages)
- Total: 252 partners with 4 data points each

**Prompt pattern:**
> "Are you able to generate a list of all the partners on their marketplace [URL]?"

**What Claude does:** Navigates the site, reads the DOM, extracts structured data, handles pagination automatically.

**Reusable for:** Any partner directory, app marketplace, or vendor ecosystem that's publicly accessible on the web.

---

### Step 2: Build the Base Scoring Rubric

**What you're doing:** Creating a scoring formula that weights the raw data fields.

**Default base criteria:**
| Criteria | What it measures | Default weight |
|----------|-----------------|----------------|
| Tier weight | Partner's status in the ecosystem (Premier, Advantage, Growth, etc.) | Variable by tier |
| NAM region bonus | Whether they operate in North America | +2 pts |
| Technology type bonus | Technology partners vs. consulting/SI partners | +2 pts |
| Enterprise penalty | Deprioritize massive corporations unlikely to be BD targets | -1 pt |

**Prompt pattern:**
> "Prioritize first, then go deep on the top 30-50. Give me an option to run the rest in batches later."

**What Claude does:** Assigns a numeric score to every partner, sorts them into Batch 1 (enrich now), Batch 2 (enrich later), Batch 3 (lowest priority). Color-codes in the spreadsheet.

---

### Step 3: Enrich with Firmographic Data

**What you're doing:** Pulling company details (revenue, headcount, HQ, description, industry) from Apollo or other data sources.

**Tools used:**
- **Apollo.io Bulk Org Enrichment** (10 companies per API call, available on free plan)
- **Web search** for companies Apollo doesn't cover
- **HubSpot CRM search** to check for existing contacts/companies

**Data points captured per company:**
- Company description (what they actually do)
- Revenue
- Employee count
- HQ city/state/country
- Phone number
- LinkedIn URL
- Website
- Industry classification
- Departmental headcount breakdown

**Prompt pattern:**
> "Can you try enrichment with my HubSpot and the web?"

**Note:** Apollo's People Search (individual contacts) requires a paid plan. Org enrichment works on free tier. For decision makers, use Apollo's web UI with free monthly credits, or LinkedIn Sales Navigator.

---

### Step 4: Research the Target Company's Value Prop

**What you're doing:** Understanding exactly what the company you're selling on behalf of (e.g., Tivly) does, so the scoring criteria match their ideal customer profile.

**Prompt pattern:**
> "I want to build a list out for Tivly, so go look at the company and bring in criteria to the scoring panel that makes your rubric more fitting for the product/service that Tivly offers."

**What Claude does:**
- Researches the company via web search
- Identifies their core product, target market, and value proposition
- Creates custom scoring criteria aligned to their ICP
- Pre-scores each partner in the ecosystem against those criteria

**Tivly example criteria:**
| Criteria | What it measures | Why it matters for Tivly |
|----------|-----------------|--------------------------|
| Distribution Alignment | Works in policy/underwriting/digital distribution | Tivly generates leads for new business, not claims |
| SMB Commercial Focus | Focused on small commercial lines | Tivly's marketplace is SMB-focused |
| Digital CX / Acquisition | Improves digital customer experience | Tivly's value prop is simplifying the buying journey |
| Lead Gen Compatibility | Could benefit from Tivly's lead flow | Direct product-market fit signal |

---

### Step 5: Build the Interactive Scoring Panel

**What you're doing:** Creating a live, adjustable dashboard where you can change weights and filters to see how the list reshuffles.

**What the panel includes:**
- **Weight sliders** for each Tivly-specific criterion (0-10)
- **Base weight sliders** for tier, NAM bonus, tech bonus, enterprise penalty
- **Filter dropdowns** for tier, type, region, and min score
- **Search** by partner name
- **Sortable columns** (score, name, Tivly fit, tier)
- **Detail panel** showing company intel when you click a row
- **Dot visualization** for each Tivly criteria (5-dot rating)
- **CSV upload** to load a new partner list into the same framework
- **CSV export** to download the scored/filtered list

**The scoring panel is reusable.** Upload any CSV with columns for Partner Name, Type, Region, and Tier. The Tivly-specific criteria scores default to 2/5 for new entries and can be manually adjusted.

---

### Step 6: Export, Batch, and Execute

**Outputs from this workflow:**

1. **Full spreadsheet** (all 252 partners, color-coded by batch, enriched firmographics for Batch 1)
2. **Interactive scoring panel** (React artifact, runs in Claude, adjustable in real time)
3. **Scored CSV export** (downloadable from the panel, import into HubSpot or any CRM)

**Batch execution model:**
- **Batch 1** (top 35): Fully enriched. Ready for decision maker research and outreach.
- **Batch 2** (next 85): Partially enriched. Run in next session: "Run Batch 2 enrichment."
- **Batch 3** (remaining 132): Low priority. Run when Batches 1-2 are worked.

---

## How to Replicate This for Any Ecosystem

### Change the marketplace
Replace the URL in Step 1 with any partner directory:
- Salesforce AppExchange
- Duck Creek Marketplace
- Majesco Partner Ecosystem
- Any vendor's partner page

### Change the target company
Replace "Tivly" in Step 4 with any company. Claude will research them and generate custom scoring criteria.

### Change the scoring criteria
The panel's sliders let you adjust on the fly. For a completely different use case (e.g., scoring for competitive mapping instead of BD), tell Claude:
> "Rebuild the scoring criteria for competitive intelligence instead of BD prospecting."

---

## Tools Required

| Tool | Purpose | Required? |
|------|---------|-----------|
| Claude (claude.ai) | Orchestration, research, scoring, artifact creation | Yes |
| Claude in Chrome extension | Marketplace scraping | Yes (for scraping) |
| Apollo.io (free plan) | Company firmographic enrichment | Recommended |
| HubSpot | Check existing contacts, CRM import | Optional |
| LinkedIn Sales Navigator | Decision maker identification | Optional |

---

## Prompt Sequence (Copy/Paste Ready)

**1. Harvest:**
> "Are you able to generate a list of all the partners on their marketplace [URL]?"

**2. Score + Batch:**
> "Prioritize first, then go deep on top 30-50. Give me an option to run the rest in batches later."

**3. Enrich:**
> "Can you try enrichment with my HubSpot and the web? Establish 3 decision makers at each company."

**4. Customize for target company:**
> "I want to build a list out for [COMPANY NAME], so go look at the company and bring in criteria to the scoring panel that makes your rubric more fitting for the product/service that [COMPANY NAME] offers."

**5. Build the panel:**
> "Build a reusable scoring panel with dropdown filter selections to change how I score and categorize a company."

**6. Export + Execute:**
> "Export the scored list as a CSV. Run Batch 2 enrichment."

---

*This workflow was built live in a single Claude session. Total deliverables: 1 raw spreadsheet, 1 enriched spreadsheet, 2 interactive scoring panels, and this documentation.*
