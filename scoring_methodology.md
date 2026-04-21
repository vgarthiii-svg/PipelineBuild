# Scoring Methodology
## B2B BD Matchmaker

This document defines how the Matchmaker Score is calculated. All formulas are transparent and adjustable by the user.

---

## The Two Dimensions

Every match is scored on two independent dimensions:

### Dimension 1: Product-Market Fit (PMF)
How well does this partner's business align with the target company's needs?

**Composed of:**
- **Base modifiers** (always applied):
  - Ecosystem tier weight (uses the partner ecosystem's own tier labels)
  - NAM region bonus (+2 default if target company is US-based)
  - Technology partner bonus (+1 default, prioritizes tech over consulting/SI)
  - Company size alignment (penalty for massive enterprise if target sells to mid-market)

- **Custom criteria** (4-6, generated per target company):
  - Each scored 0-5 per partner
  - Each weighted 1-10 by importance (set during criteria generation, adjustable by user)
  - Derived from the target company's products, ICP, and value chain position

**PMF Calculation:**
```
Raw PMF = (sum of base modifiers) + (sum of each criterion_score x criterion_weight / 5)
Normalized PMF = (Raw PMF / Max Possible PMF) x 100
```

### Dimension 2: Relationship Strength (RS)
How well positioned is the user to make this introduction?

**Scored 0-5 per partner:**
- 5 = Inner Circle (could call today, get a callback)
- 4 = Strong (warm enough for a direct ask)
- 3 = Warm (they'd know your name)
- 2 = Light (LinkedIn connection or one-hop intro available)
- 1 = Aware (know of them, no direct contact)
- 0 = Cold (nothing)

**RS Calculation:**
```
Normalized RS = (relationship_score / 5) x 100
```

---

## The Matchmaker Score

**Matchmaker Score = (PMF x W1) + (RS x W2)**

Default weights: W1 = 0.6, W2 = 0.4

### Why 60/40?

The system deliberately overweights fit but gives meaningful credit to relationships. A warm intro to a good-fit company beats a cold approach to a perfect-fit company in the real world.

### Weight adjustment commands:
- "Reweight to 80/20 fit over relationship" (pure prospecting mode)
- "Reweight to 50/50" (maximize existing network)
- "Reweight to 30/70 relationship over fit" (network-first, good for conference follow-ups)

---

## Tier Weight Defaults

These map to common partner ecosystem tier systems. Adjust if the ecosystem uses different labels.

| Tier | Default Weight |
|------|---------------|
| Global Strategic | 6 |
| Global Premier | 5 |
| Premier | 5 |
| Advantage | 4 |
| Select | 2 |
| Growth | 1 |
| Access | 0 |

---

## Custom Criteria Generation Rules

When generating criteria for a new target company, follow these rules:

1. **Derive from the value chain.** Look at what the target company's customers need upstream and downstream. Partners that fill those adjacent needs are the best matches.

2. **Weight toward the company's primary revenue driver.** If the company makes 80% of its money from lead generation, the "lead gen compatibility" criterion should carry the highest weight.

3. **Include at least one "buyer alignment" criterion.** Does the partner sell to the same buyer type as the target company? If the target sells to SMB carriers, a partner that only serves enterprise reinsurers is a poor fit regardless of product overlap.

4. **Include at least one "product complementarity" criterion.** Does the partner's product naturally pair with the target company's offering? Think: "Would a carrier want to buy both of these together?"

5. **Cap at 6 criteria.** More than 6 dilutes the signal. If you can't decide, merge similar criteria or drop the weakest one.

6. **Present to the user before scoring.** They know their business better than the model does. Let them approve, adjust weights, or swap criteria before running the full ecosystem score.

---

## Scoring Output Tiers

After scoring, partners are bucketed:

| Matchmaker Score | Tier | Action |
|-----------------|------|--------|
| 70+ | Hot | Priority outreach. Research decision makers. Prep intro scripts. |
| 50-69 | Warm | Secondary outreach. Worth an introduction if relationship exists. |
| 30-49 | Monitor | Track for changes (new product launches, leadership changes). |
| Below 30 | Pass | Not a fit for this target company. May fit a different one. |
