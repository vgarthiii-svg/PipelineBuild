# Identity Filters: Complete Reference Guide
## BD Pipeline Agent

**What this is:** Everything you need to know about using Identity Filters effectively. Identity Filters are the first layer of the 4-layer scoring engine - a hard gate that disqualifies prospects before any scoring math happens.

---

## What Identity Filters Do

Think of filters as your **"hell no" list** - criteria that instantly disqualify a company regardless of how good their other scores might be.

Examples:
- "Tivly only works with commercial P&C, never Life or Health Insurance"
- "I don't care how perfect a match a 3-person startup is, too risky to partner"
- "This client only operates in NJ/NY/PA - anyone else is a waste"

Filters don't delete data. They just hide companies from your Hot/Warm/Monitor/Pass ranking so you focus on legitimate candidates.

---

## How Filters Work Technically

Each client has their own filter with these optional rules:

| Filter | What It Does | Example |
|--------|--------------|---------|
| **Allowed Business Models** | Only include companies matching these models | B2B, SaaS, hybrid (excludes B2C consumer companies) |
| **Allowed Stages** | Only include companies at these stages | growth, mature, enterprise (excludes startups) |
| **Min Employees** | Exclude companies below this size | 10+ (excludes tiny shops) |
| **Max Employees** | Exclude companies above this size | 50,000 (excludes mega-carriers) |
| **Excluded Verticals** | Reject specific industries | "Life Insurance", "Health Insurance" |
| **Required Verticals** | Only include these industries | "P&C Insurance" (rejects everything else) |

**Key rule:** Companies only need to **fail one rule** to get filtered out.

---

## Scope: Per Client, Applied to All

- **Each client has their own filter** (Tivly's filter is different from Circle AI's filter)
- When you save a filter, the system evaluates **every company in that client's pipeline**
- Companies that **fail any rule** get marked as `filtered` tier
- Companies that **pass all rules** get scored normally (Hot/Warm/Monitor/Pass)

---

## What "Filtered" Means in the Pipeline Table

When you apply a filter:

- Filtered companies are **NOT deleted** - they stay in the pipeline
- Their tier badge changes to `filtered` (grayed out, strikethrough style)
- They're **excluded from the main rankings** so your Hot/Warm/Monitor/Pass counts only reflect eligible companies
- You can view them by clicking the **"Filtered"** tier button at the top of the table
- They show a `filter_reason` explaining why they were excluded (e.g., "Business model 'B2C' not in allowed: ['B2B', 'SaaS', 'hybrid']")

---

## Where to Edit Filters

On the dashboard, below the three control layer cards, there's a collapsible **"Identity Filters"** section.

1. Click **Expand** to see the current filter
2. Use the checkboxes and inputs to modify
3. Click **"Save & Rescore"** to apply

---

## What Happens When You Change the Filter

### Scenario 1: Loosen the filter (remove a rule)
- Previously filtered companies come back into scoring
- They get evaluated against PMF criteria
- Get assigned Hot/Warm/Monitor/Pass based on their scores

### Scenario 2: Tighten the filter (add a rule)
- Companies that now fail the rule get moved to filtered
- Hot/Warm/Monitor/Pass counts decrease
- Those companies are hidden from your main view

### Scenario 3: Switch clients
- You load Client B's filter (completely different from Client A's)
- Client B's pipeline is evaluated against Client B's filter
- Same 46+ companies, different filter result

---

## Concrete Example: Tightening Tivly's Filter

Say you set Tivly's filter to `Min Employees: 100`:

**Before:** 46 companies in pipeline
- 10 Hot, 15 Warm, 18 Monitor, 3 Pass

**After filter applied:**
- 8 companies have < 100 employees → filtered
- 38 companies remain eligible for scoring
- Your counts update: maybe 8 Hot, 13 Warm, 14 Monitor, 3 Pass, **8 Filtered**

The 8 filtered ones stay in the database. If you lower the filter to `Min Employees: 10`, they come back.

---

## Current Setup: Tivly's Filter (from seed data)

```
Business models: B2B, SaaS, hybrid
Stages: growth, mature, enterprise
Min employees: 10
Excluded verticals: Life Insurance, Health Insurance
```

This makes sense because Tivly is commercial P&C focused, and tiny startups can't provide the partnership volume they need.

---

## Practical Filter Templates by Client Type

### For a Carrier Client (Tivly-style, selling distribution to carriers)
```
Business Models: B2B, hybrid
Stages: growth, mature, enterprise
Min Employees: 10+
Excluded Verticals: Competitor lines (Life/Health if P&C focused)
Required States: Only their licensed states
```

### For a Tech/SaaS Client (like Circle AI, selling software to agencies)
```
Business Models: B2B, SaaS
Stages: growth, mature
Min Employees: 20+ (too small agencies don't adopt new software)
Required Verticals: P&C Insurance, InsurTech
```

### For a Fintech Client (like Flex, payment infrastructure)
```
Business Models: B2B, hybrid
Stages: mature, enterprise
Min Employees: 100+ (too small = payment volume too low)
Required Verticals: P&C Insurance, Specialty Insurance
```

### For a Wholesale/MGA Client
```
Business Models: B2B
Stages: mature, enterprise
Min Employees: 50+
Required States: Overlap with client's operating states
```

---

## When NOT to Use Filters

- **Don't filter for soft preferences** - if you "prefer" mid-market but would still take SMB deals, use scoring criteria weights instead of a hard filter
- **Don't filter based on relationship strength** - RS already handles that dimension
- **Don't filter too aggressively early** - you might hide surprise good matches; tune over time
- **Don't filter based on timing/intent** - that's what the Intent Multiplier layer is for

---

## Filters vs. Criteria: Know the Difference

| | Filters | Criteria |
|--|---------|----------|
| Effect | Hard pass/fail | Graduated 0-5 score |
| Purpose | Disqualify (cut noise) | Rank (find best) |
| Reversible | Always yes | Yes, recalc |
| Visible in rankings | Filtered out | Still shown |

**Rule of thumb:**
- Use **filters** for things where you'd say "never in a million years"
- Use **criteria** for things where you'd say "this matters more/less"

---

## Quick Test to See Filters in Action

1. Open Tivly's pipeline, note the current Hot/Warm counts
2. Click the **"Identity Filters"** panel → Expand
3. Change **Min Employees** from `10` to `1000`
4. Click **"Save & Rescore"**
5. Watch the counts drop - many companies will now show "Filtered" tier
6. Click the **"Filtered"** button at top of table to see which ones got cut and why
7. Change it back to `10` and Save & Rescore → they return

---

## Recommended Starting Strategy

**Start minimal, add constraints over time.**

For new clients, try setting just:
- Required vertical: P&C Insurance (or specific lines you serve)
- Min employees: 10

Then score your pipeline, look at the results, and ask "am I seeing companies that are clearly wrong for this client?"

- If **yes**: add another filter rule
- If **no** (rankings already feel right): leave it alone

Over time, you'll dial in the right set of filters for each client based on real experience and deal outcomes.

---

## Troubleshooting

**"All my companies are showing as Filtered"**
- Your filter rules are too strict. Loosen them, starting with the most restrictive (employee counts, required verticals).

**"None of my filters seem to be working"**
- Check that companies have the data the filter uses (industry_vertical, business_model, employees). If those prospect fields are empty, the filter can't evaluate them. Run "Enrich All" to populate firmographic data first.

**"I set a filter but my Hot/Warm counts didn't change"**
- Click "Save & Rescore" (not just "Save Filters"). The rescore is what moves companies to/from the filtered tier.

**"Companies are filtered for the wrong reasons"**
- Click on a filtered company in the table to see the `filter_reason` field. If the reason is wrong, the prospect's metadata is wrong. Fix the prospect data, not the filter.

---

## Summary: The Layer-1 Filter in the 4-Layer Scoring Engine

```
┌──────────────────────────────────┐
│  LAYER 1: IDENTITY FILTER        │  ← This is what this doc is about
│  Hard gate - pass/fail           │
└──────────────────────────────────┘
              │
              ▼ (only if passed)
┌──────────────────────────────────┐
│  LAYER 2: CAPABILITY (PMF)       │
│  Criteria-weighted 0-100 score   │
└──────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────┐
│  LAYER 3: FRICTION COEFFICIENT   │
│  Behavior mismatch penalty       │
└──────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────┐
│  LAYER 4: INTENT MULTIPLIER      │
│  Recency/urgency boost           │
└──────────────────────────────────┘
              │
              ▼
     FINAL MATCHMAKER SCORE
```

If a company fails Layer 1, it never reaches Layers 2-4. It just shows up in the "Filtered" tier. Saves you from wasting mental energy on bad fits.

---

*Generated for Vinnie Garth, Vinsational Consulting. Reference document for the BD Pipeline Agent.*
