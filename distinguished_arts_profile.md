# Client Profile: Distinguished Fine Art & Collectibles

The main account / scoring lens. The pipeline is scored against this profile to find the best-matching "other businesses" (partners, referral sources, and distribution). Format mirrors the Tivly and Decerto profiles.

---

## Distinguished Fine Art & Collectibles

*Source: distinguished.com (Art & Collectible Insurance program pages and broker/expert articles).*

**Confirmed coverage facts (distinguished.com):** property-damage policy protecting collections on- and off-premises — at home, on exhibition, in transit, or in storage; **nail-to-nail** transit (from removal at origin through packing, shipping, consolidation, and reinstallation); capacity up to **$125M with no aggregation concerns**; available in **all 50 states**; distributed through brokers (they run a **Broker Connect Portal** and a brokers' Q&A), and connect clients/brokers with appraisers, restoration specialists, and other services as a value-add.

### Snapshot
| Field | Value |
|-------|-------|
| Name | Distinguished Fine Art & Collectibles (a program of Distinguished Programs) |
| What | Specialty insurance program (MGA / program manager) for fine art and collectibles |
| Underwriting partner | Core Specialty |
| Launched | 2023 |
| Capacity | Collections up to **$125M** |
| HQ | New York, NY |
| Leadership | Patrick Drummond (program lead); Erika Witler, Skyler Stone, Alison Sweeney, Nonie Tompkins, Michelle Stegmann; Stacy Button (Distinguished) |
| Website | distinguished.com (Art & Collectible Insurance) |

### What they sell
1. **Fine Art Insurance:** paintings, sculptures, works on paper for private collectors, dealers, galleries, museums, corporate collections.
2. **Collectibles Insurance:** wine, coins, stamps, rare books, comics, trading/sports cards, sneakers, couture, watches, memorabilia.
3. **Coverage for the trade:** dealers, galleries, advisors, auction houses, restorers, framers, shippers — including transit, storage, and exhibition coverage.

*Primary revenue driver:* specialty premium, distributed through retail insurance brokers (wholesale MGA model).

### Who they sell to / how it reaches market
- **Distribution channel (primary buyer):** retail P&C insurance brokers and agents, especially HNW / private-client practices. Distinguished is wholesale — brokers place the business.
- **End insureds:** HNW/UHNW private collectors, art dealers, galleries, art advisors, artists, museums, corporate collections, auction houses, foundations and estates.

### Problems they solve
1. Protecting high-value, often irreplaceable physical assets in transit, storage, and exhibition.
2. Coverage tailored to volatile-value collectibles the standard market mishandles.
3. Expert appraisal reviews, claims, and access to a restoration/shipping/advisory network.

### The matchmaking thesis (what "other businesses" means here)
Distinguished states (distinguished.com) that it "collaborates with an extensive network of industry professionals, including specialty fine art insurance **brokers, advisors, appraisers, shippers, restorers, and attorneys**." That named network is the matchmaking target. A business is a strong match when it **touches high-value collections or the people who own them**, and can therefore either (a) generate insurable business, (b) refer it, or (c) distribute the program. Three target rings:
- **Fine-art ecosystem:** auction houses, galleries/dealers, art logistics/shippers, storage, appraisers, restorers, collection-management platforms.
- **HNW-adjacent referral:** wealth managers, family offices, private banks, trust & estate attorneys.
- **Distribution:** HNW / private-client P&C brokers and agencies.

### Scoring criteria (PMF dimension)
*Each scored 0–5 per business, weighted 1–10.*

| # | Criterion | What it measures | Weight |
|---|-----------|-----------------|--------|
| 1 | HNW/UHNW collector access | Serves high-net-worth clients who own insurable collections | 10 |
| 2 | Referral or distribution potential | Can refer insurable collections or place/distribute the program (brokers, advisors, appraisers, shippers) | 9 |
| 3 | Art & collectibles ecosystem fit | Sits in the fine-art/collectibles value chain | 8 |
| 4 | Insurable-asset concentration | Regularly handles or holds high-value physical pieces needing coverage | 7 |
| 5 | Prestige / trust alignment | Premium, reputation-first brand consistent with "Distinguished" | 5 |

### Relationship strength (RS dimension)
Warm where Vinnie / Distinguished already has broker, gallery, or advisor relationships. Set per account as intros are confirmed.

### Target ecosystem
See `fine_art_ecosystem.csv` — a starter list of real businesses across auction, gallery, logistics, storage, appraisal, collection-management, wealth/family-office, and HNW-broker categories, pre-scored for a first pipeline run. Enrich and expand as needed.

---

## Rubric v2 — Distribution / channel prospects

Modeling an insurance-distribution prospect list showed the v1 art-ecosystem criteria don't fit. Insurance prospects are scored on a **channel** rubric led by **distribution segment** — where they sit in the chain that moves fine-art business to a wholesale MGA like Distinguished. Tag every prospect **Class = Channel** (sells/places the coverage) or **Class = Referral** (originates insurable collections; the v1 art-world 26).

### Distribution segment taxonomy (the lead dimension)
| Segment | Role to Distinguished | Base segment score (0–5) |
|---------|----------------------|--------------------------|
| Retail — Private Client specialist | Owns the HNW client; places up to wholesale/MGA | 5 |
| Agency network / aggregator | One appointment = many retail agencies' HNW books (leverage) | 5 |
| Wholesale broker | Routes complex/overflow fine art to MGAs | 4 |
| MGA / Program — no own fine-art program | Can place or refer; partner for capacity | 4 |
| Retail — generalist | Has affluent clients but no PC specialization | 3 |
| MGA / Program — **own** fine-art program | Competes; channel conflict | 2 |
| HNW carrier with own fine-art program | Self-underwrites; competitor | 1 |
| Direct / captive / mass-market carrier | Not a placement channel | 0 |

### Channel rubric (PMF, 6 criteria)
| # | Criterion | What it measures | Weight |
|---|-----------|-----------------|--------|
| 1 | **Distribution segment fit** | Position in the chain (from the taxonomy above) | 10 |
| 2 | Fine-art/collections placement capability | Has a Private Client/HNW desk that actually places fine art & collectibles | 9 |
| 3 | Channel independence | Does NOT run a competing fine-art program (5 = pure distributor, 0 = full competitor) | 8 |
| 4 | HNW reach & volume | Breadth/scale of affluent book or downstream agents | 7 |
| 5 | Placement authority | Binding authority / Lloyd's coverholder — can move business directly | 5 |
| 6 | Prestige / service alignment | Concierge private-client posture fitting "Distinguished" | 4 |

RS (relationship) stays separate — warm ties (e.g., High Street Brokers / Tompkins) lift the score.

Channel prospects live in `distinguished_channel_prospects.csv`, segment-tagged and scored.

---

## Vinnie's relationship
TBD — set as you confirm warm intros into these businesses.
