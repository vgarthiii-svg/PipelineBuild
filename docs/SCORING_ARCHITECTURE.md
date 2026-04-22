# BD Pipeline Agent — Scoring Architecture

> Where scoring criteria sit in the system and how they flow into a final Matchmaker Score.

## System diagram

```
                          ┌─────────────────────────────────┐
                          │      CRITERIA LIBRARY           │
                          │   (20 reusable criteria in 4    │
                          │    groups — shared across all   │
                          │    lenses)                      │
                          │                                 │
                          │   Group: Buyer Alignment        │
                          │     • Target Buyer Overlap  w5  │
                          │     • Segment Fit           w4  │
                          │   Group: Product Complement     │
                          │     • Adjacent Offering     w5  │
                          │     • Integration Surface   w4  │
                          │   Group: Distribution           │
                          │     • Channel Compatibility w5  │
                          │   Group: Strategic              │
                          │     • Partnership Maturity  w3  │
                          │     ... (20 total)              │
                          └──────────────┬──────────────────┘
                                         │ toggle on/off
                                         │ per-lens, adjust weight
                                         ▼
┌─────────────────┐         ┌─────────────────────────────────┐
│   COMPANY POOL  │         │      SCORING CRITERIA           │
│  (prospects)    │         │  (per-lens — one row per lens   │
│                 │         │   × per enabled criterion)      │
│  • Tivly        │         │                                 │
│  • Circle AI    │◄────────│   client_id ──► lens's criteria │
│  • Flex         │  lens   │   library_id ─► source template │
│  • Erie         │  owns   │   weight 1-10 (tunable)         │
│  • Shelter      │◄────────│   active true/false             │
│  • Lemonade     │         │   sort_order                    │
│  • ... (55)     │         │                                 │
└────────┬────────┘         └─────────────────────────────────┘
         │                                   │
         │ any company                       │ criteria define WHAT
         │ can be selected                   │ to score against
         │ as lens                           │
         ▼                                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    PIPELINE ENTRIES                          │
│              (one row per lens × per prospect)              │
│                                                              │
│   lens: Tivly                                                │
│   ┌───────────┬──────────────────────────────────────────┐  │
│   │  Erie     │ criterion_scores (0-5 per criterion)     │  │
│   │  Shelter  │   Buyer Overlap      → 4  "reasoning..."  │  │
│   │  Lemonade │   Segment Fit        → 3  "reasoning..."  │  │
│   │  ...      │   Adjacent Offering  → 5  "reasoning..."  │  │
│   └───────────┴──────────────────────────────────────────┘  │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
       ╔══════════════════════════════════════════════╗
       ║         4-LAYER SCORING ENGINE                ║
       ║                                                ║
       ║  Layer 1: IDENTITY FILTER                     ║
       ║    Hard gate (size, geo, type). Pass/fail.    ║
       ║              │                                 ║
       ║              ▼                                 ║
       ║  Layer 2: PRODUCT-MARKET FIT (PMF)  ◄────────╫─── criterion_scores
       ║    PMF = Σ(score/5 × weight) / Σweight × 100  ║    aggregate here
       ║              │                                 ║
       ║              ▼                                 ║
       ║  Layer 3: FRICTION COEFFICIENT                ║
       ║    Behavior profile compatibility (0-1).      ║
       ║              │                                 ║
       ║              ▼                                 ║
       ║  Layer 4: INTENT MULTIPLIER                   ║
       ║    Active buying signals (1.0-1.5×).          ║
       ║              │                                 ║
       ║              ▼                                 ║
       ║  MATCHMAKER SCORE                              ║
       ║    (PMF×W₁ + RS/5×100×W₂) × Friction × Intent ║
       ║              │                                 ║
       ║              ▼                                 ║
       ║  TIER: Hot / Warm / Monitor / Pass / Filtered ║
       ╚══════════════════════════════════════════════╝
```

## Database tables involved

```
criteria_library          scoring_criteria          criterion_scores
(20 templates)            (per-lens, active set)    (per entry, per crit)
    │                            │                         │
    │  copied from ──────────────►                          │
    │                            │                         │
    │                            │  applied to             │
    │                            │  each row in ──────────►│
    │                            │  pipeline               │
    ▼                            ▼                         ▼
┌─────────────┐          ┌───────────────┐       ┌─────────────────┐
│ id          │          │ id            │       │ id              │
│ group_name  │          │ client_id  FK │       │ pipeline_entry_id│
│ name        │          │ library_id FK │       │ criterion_id  FK│
│ description │          │ name          │       │ score (0-5)     │
│ default_wt  │          │ weight (1-10) │       │ reasoning       │
│ sort_order  │          │ active        │       │                 │
└─────────────┘          │ sort_order    │       └─────────────────┘
                         └───────────────┘
```

## Key concepts

**Criteria are per-lens, not global.** When you pick Tivly as the lens, the pipeline gets scored against Tivly's enabled criteria. When you pick Lemonade, the pipeline re-scores against Lemonade's criteria (which may be a different subset with different weights). Each combination is cached in `criterion_scores` so you're not rescoring everything every time.

**Criteria feed ONLY the PMF layer.** The other three layers come from different data sources:

| Layer | Source | File |
|---|---|---|
| Identity Filter | `identity_filters` table (one per lens) | `app/scoring.py :: run_identity_filter` |
| PMF | `scoring_criteria` + `criterion_scores` | `app/scoring.py :: calculate_pmf` |
| Friction | `behavior_profiles` table (one per prospect) | `app/scoring.py :: calculate_friction_coefficient` |
| Intent | `intent_signals` table (many per prospect) | `app/scoring.py :: calculate_intent_multiplier` |

## How criteria get populated

Two paths:

1. **Toggle from the library** — click a criterion tile in the Scoring Criteria panel. A row is created in `scoring_criteria` for the current lens, referencing the library template. Clicking again toggles `active` false without deleting (so weight adjustments persist).

2. **Auto-seeded defaults** — on first lens selection (via `promote_prospect_to_client`), the system creates 4-5 default criteria tuned to the company's inferred type (insurance carrier, tech, fintech). These are added directly to `scoring_criteria` without a `library_id`.

## How scores get computed

Flow for one pipeline entry:

```python
# app/scoring.py (simplified)
scores_and_weights = []
for criterion in lens.active_criteria:
    heuristic = infer_score(prospect, criterion, lens.profile)   # 0-5
    db.add(CriterionScore(pipeline_entry_id=entry.id,
                          criterion_id=criterion.id,
                          score=heuristic.score,
                          reasoning=heuristic.reason))
    scores_and_weights.append((heuristic.score, criterion.weight))

pmf = calculate_pmf(scores_and_weights)                          # 0-100
passed, reason = run_identity_filter(prospect, lens.filter)      # bool
friction = calculate_friction_coefficient(lens.behavior, prospect.behavior)  # 0-1
intent = calculate_intent_multiplier(prospect.intent_signals)    # 1.0-1.5

matchmaker = calculate_matchmaker(pmf, relationship_score, friction, intent)
tier = assign_tier(matchmaker)
```

## Related files

- `app/models.py` — `CriteriaLibrary`, `ScoringCriterion`, `CriterionScore` ORM models
- `app/scoring.py` — All four layer calculations
- `app/routers/clients.py` — Criteria CRUD + library toggle endpoints
- `app/routers/pipeline.py` — Scoring endpoints (`/score`, `/score-all`)
- `static/index.html` — Scoring Criteria panel (grouped toggle tiles)
- `static/app.js` — `toggleLibraryCriterion`, `rescoreAfterToggle`, weight sliders
