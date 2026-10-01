# Distinguished Fine Art & Collectibles — Pipeline Framework

Source of record: **DFAC US Prospect Universe** (GTM Distribution Plan, First 90 Days, rev 4) + the 2027 BD Comp Plan Appendix A. This file defines the pipeline; the scored data lives in `dfac_prospect_universe.csv` and exclusions in `dfac_excluded.csv`.

## Objective & the two books
Distinguished is a fine-art & collectibles **MGA that distributes through brokers**, so every prospect is a **distribution partner** — never an end client, never a carrier. Two books:
- **West Region** — Vinnie's regional broker development (registrations → submissions → bound policies → active writers). Kristen Ostermayer holds the East.
- **National Account** — the whole-US track. An org becomes a national account only on the Appendix A mechanism (an intranet/portal placement reaching all producers). **There are currently none.**
- **Both** — most wholesalers; carries a regional tier and a national gate.

## The seven segments
| Segment | Who | Motion / cycle |
|---|---|---|
| **T1 Major** | West offices of national brokerages & large regionals (10+ producers, named practice leader) | Practice-leader sale → office activation; 3–9 mo |
| **T2 Multi-office** | Multi-office regional/specialty brokerages in the West (3–9 offices) | Practice-leader sale → office activation; 2–6 mo |
| **T3 Specialist** | Private-client boutiques, museum/nonprofit practices, dealer/gallery specialists | Single-producer, direct; 3–10 wks — **highest hit rate** |
| **T4 Wholesale** | Regional wholesalers, MGAs, surplus-lines brokers | Desk-level sale → joint retail campaign; 2–6 mo, compounds |
| **National Brokerage** | Appendix A national brokerages/networks | Ends in an intranet placement; 6–18 mo |
| **National Wholesaler** | Appendix A wholesalers | Their market directory already exists — most achievable mechanism |
| **Direct Writer** | Appendix A direct writers (captive/affinity) | Product/partnership exec; procurement in path; ~12 mo |

*(T5 Opportunistic exists in the GTM plan but is reactive — not populated here.)*

## The four forms (Forms-fit column: P / C / D / M)
- **P — Personal:** private collector households. Ask for private client / HNW / family office.
- **C — Corporate:** company-owned collections. Ask for commercial property / middle market.
- **D — Dealer:** galleries, dealers, art businesses. Ask for specialty commercial / inland marine.
- **M — Museum:** museums, nonprofits, higher ed, public entities. Ask for the nonprofit / public-entity practice.

Two or more forms scores the full 20 on Segment fit (a multi-form broker produces repeat submissions).

## The 100-point scoring model
Base Score is a plain sum, never weighted, nobody types it:

| Dimension | Max | Bands |
|---|---|---|
| Premium concentration | 30 | 30 at $500K+ placeable FA premium, 20 at $150–500K, 10 at $50–150K, 0 below |
| Segment fit | 20 | 20 for 2+ forms, 12 for one strong form, 4 adjacent |
| Distribution leverage | 20 | 20 for 50+ producers, 14 for 10–49, 8 for 3–9, 3 for one |
| **Territory gap** *(blue — your input)* | 15 | 15 no producing broker in metro/state, 8 thin, 0 well-covered (needs Patrick's D1 map) |
| **Access path** *(blue — your input)* | 10 | 10 warm intro, 6 second-degree, 3 cold with named human, 0 none |
| Conflict-free | 5 | 5 no competing program/MGA/East tie, 2 partial, 0 conflicted |

Territory gap and Access path are **placeholders until division data is filled** — so every score here is a **floor**. Checking Patrick's, Nonie's and Kristen's networks is the cheapest 7 points in the model.

## Weights, Waves, Rank
- **Segment weight** (Segment Weights tab) multiplies Base → **Weighted Score**. Ships at **1.00 across all seven** (Weighted = Base). Above 1.00 promotes a segment, 0 parks it.
- **Waves** off Weighted Score: **Wave 1 ≥ 70** (worked continuously, ~25 orgs at capacity), **Wave 2 = 45–69** (lighter cadence), **Wave 3 < 45** (nurture, re-scored at 90 days). Breakpoints are live input cells.
- App tiers map Wave 1 → **hot**, Wave 2 → **warm**, Wave 3 → **monitor**.

## Conflict policy & exclusions
A firm that **runs or fronts its own fine-art capability scores 0 on conflict-free and is excluded** — the conversation is displacement, not a channel. Full list in `dfac_excluded.csv`. Key exclusions that correct earlier drafts:
- **Risk Strategies / DeWitt Stern / One80** — national fine-art practice + captive wholesaler. EXCLUDE.
- **Gallagher, Alliant (Mark Recht), Aon / Huntington T. Block, WTW, Marsh PCS/MMA** — own fine-art practices. EXCLUDE / Appendix A flag.
- **RT Specialty** — national personal-lines shelf is effectively exclusive to Private Client Select (AIG). Appendix A flag, recommend drop.
- **Arrowhead** — in the universe but CONFLICTED (own Valuable Articles program).
- **Absorbed, do not source:** Gerald J. Sullivan → Amwins, Anderson & Murison → Monarch/SPG, All Risks → CRC. Work the parent.
- **Not a broker (separate referral list):** appraisers/advisors (Winston Art Group, The Fine Art Group, etc.) — see `fine_art_ecosystem.csv`, kept as the upstream referral-source list, not part of the broker pipeline.

## House terminology
Broker (never "agent") · Brokerage (never "agency") · Registered (never "appointed") · **Broker Connect** (portal; sub-$500K binds straight-through in 24–48h) · **Loss in value** (the wedge — pays restoration cost *plus* post-restoration market-value drop) · **Activated broker** (3 submissions or 1 bind within 90 days) · **Gates 1–6** (national-account progression; Gate 4 Mechanism is the real predictor).

## Sourcing & loading
- `dfac_prospect_universe.csv` — 104 orgs, one row each, scored on the 100-point model with Wave + segment.
- `dfac_excluded.csv` — everything screened out, with reason and source.
- Load into the app: `python -m app.import_distinguished` (replaces the Distinguished pipeline with the universe; Wave → tier).

## Known limits
Named contacts are a second pass (Apollo) — where research surfaced a human it's in the Named-contact column as a head start. Premium bands are informed estimates, not production numbers. **Lockton** is unverified (site blocks fetching) — treat as a research to-do. The prior 39-org engine can be reconciled by name if its CSV is added.

## Vinnie's relationship
West Region book owner. Warm-network points (Access path 6–10) to be filled from Patrick's, Nonie's and Kristen's networks.
