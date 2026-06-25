# Scoring Logic

Source of truth: `backend/app/engines/scoring.py` (with
`backend/app/engines/ap_style.py` for the deterministic AP check and
`build_scoring_prompt` / `SYSTEM_SCORER` in `backend/app/ai/prompts.py`).

The scorer rates a draft across **14 categories, 0–100 each**, then computes a
single weighted overall. It combines AI judgment (via the provider) with the
**deterministic AP-style checker**, so scores are grounded and reproducible even
without an API key.

---

## The 14 scoring categories (`SCORE_CATEGORIES`)

Each category has a `label`, `desc`, and `weight`, keyed exactly as below.

| Key | Label | Weight | Description |
| --- | --- | --- | --- |
| `platform_fit` | Platform fit | 1.2 | Follows the selected platform's structure and norms. |
| `audience_fit` | Audience fit | 1.1 | Speaks to the target audience's context and pain. |
| `hook_strength` | Hook strength | 1.2 | Opening earns attention and a reason to continue. |
| `clarity` | Clarity | 1.1 | Easy to understand; one idea per line/section. |
| `conversion_strength` | Conversion strength | 1.2 | Drives the desired action; persuasive structure. |
| `seo_strength` | SEO strength | 0.9 | Keyword/intent coverage where applicable. |
| `ap_style` | AP-style alignment | 1.0 | Clarity, active voice, numerals, no hype. |
| `brand_voice` | Brand voice alignment | 1.0 | Matches the brand's voice, words-to-use/avoid. |
| `originality` | Originality | 1.0 | Fresh angle; not generic or templated. |
| `readability` | Readability | 1.0 | Plain English, good rhythm, scannable. |
| `cta_strength` | CTA strength | 1.1 | Single, clear, benefit-led call to action. |
| `research_support` | Research support | 0.9 | Grounded in current research/proof. |
| `compliance_risk` | Compliance risk | 1.0 | Higher = lower risk; no unverifiable claims. |
| `engagement_potential` | Engagement potential | 1.1 | Likely to earn comments/shares/replies. |

Note `compliance_risk` is inverted in meaning: a **higher** score means **lower**
risk.

---

## Per-category result shape

Every category resolves to a well-formed object (normalized in `score_draft`):

```json
{ "label": "<from SCORE_CATEGORIES>",
  "score": <int 0-100>,
  "working": "<what works>",
  "weak": "<what is weak>",
  "improvements": ["<actionable fix>", ...] }
```

Normalization guarantees: `score` is clamped to `0..100` (defaulting to `70` if
absent); `working` defaults to `"On-spec for this category."`; `weak` defaults to
`"Room to sharpen."`; `improvements` defaults to
`["Add a concrete, specific detail."]`. Categories the model omits are filled in
from these defaults, so all 14 keys always appear.

The scoring prompt instructs the model (via `build_scoring_prompt`) to return
`{"overall", "summary", "categories": {"<key>": {score, working, weak,
improvements}}}` and to *"Use the exact category keys provided."*

---

## Weighted-overall formula

`_weighted_overall(categories)` computes a weight-normalized average:

```
overall = round( Σ (score_k × weight_k) / Σ weight_k )
```

over every key in `SCORE_CATEGORIES` that is present in the scored categories
(missing categories are skipped, contributing to neither numerator nor
denominator). Returns `0` if total weight is `0`.

In `score_draft`, the model may supply its own `overall`. That value is used only
if it is an `int` and `> 0`; otherwise the weighted formula is applied to the
normalized categories. The final `overall` is clamped to `0..100`.

---

## AP-style category override (deterministic)

The `ap_style` category is **not trusted to the model** — it is overwritten by
the deterministic checker so the score is auditable and reproducible:

1. `ap = ap_style.check(draft_body, custom_style_rules)` runs first.
2. Its findings are passed into `build_scoring_prompt` as `ap_findings`, so the
   model is *told* what the checker flagged (transparency).
3. After normalization, `normalized["ap_style"]["score"] = ap["ap_score"]`
   (forced).
4. If there are findings, `weak` becomes the first 4 finding `rule`s joined, and
   `improvements` becomes the first 4 finding `message`s.

### The deterministic checker (`ap_style.check`)

Rule-based, built on generally known journalistic principles (it reproduces no
copyrighted stylebook text). Each finding is
`{rule, category, severity, message, matches, count}`. Checks include:

- **Hype / fluff words** (`warning`) — e.g. revolutionary, game-changer,
  cutting-edge, synergy, leverage, disrupt, seamless, robust, etc.
- **Weasel / filler words** (`info`) — very, really, just, simply, actually,
  basically, literally, "in order to", etc.
- **Passive voice** (`warning`) — flagged when ≥2 likely passive constructions.
- **Exclamation overuse** (`info`) — flagged when more than one `!`.
- **ALL-CAPS for emphasis** (`info`) — 4+ caps runs, excluding allow-listed
  acronyms (CTA, SEO, FAQ, CEO, API, AP).
- **Numeral consistency** (`info`) — spell out one–nine, figures for 10+.
- **Long sentences** (`warning`) — sentences over 30 words.
- **Unsupported strong claims** (`warning`) — a superlative (best, fastest,
  only, leading, #1, …) with no digit anywhere in the text.
- **Custom user rules** — `StyleGuideRule` rows merged in at check time, of type
  `regex` or `phrase`; invalid regex is skipped.

### AP penalty weights & `ap_score` (0–100)

The score starts at 100 and subtracts weighted penalties per finding:

```
weights = {"error": 12, "warning": 6, "info": 2}
penalty += weights.get(severity, 4) * min(count or 1, 3)   # per finding
ap_score = max(0, min(100, 100 - penalty))
```

So each finding's penalty is its severity weight times its match count, capped at
3 matches per finding. The check also returns `word_count`, `sentence_count`,
`findings`, and `passes` (`ap_score >= 80`). This full `ap` dict is returned from
`score_draft` under the top-level `ap_style` key, alongside `overall`, `summary`,
and `categories`.

---

## Fallback behavior (no AI key present)

The flow always completes, even with no API key (`MockProvider` in use):

1. **AP check always runs** — it is pure Python and independent of any provider,
   so the `ap_style` score and findings are always real.
2. **Mock scorecard** — when `provider.complete_json` hits the scoring branch
   (prompt contains `"score the following"` or `"scorecard"`), `MockProvider`
   returns `_mock_scorecard()`: every category scored `78` with on-spec
   `working`/`weak`/`improvements`, `overall: 78`, and a stock summary.
3. **`_fallback_categories`** — if the provider returns no usable `categories`
   at all, every category is seeded at `base = 74` with generic
   working/weak/improvements, then `ap_style.score` is overridden with the real
   `ap_score`.
4. **`_fallback_summary`** — used when no model summary is present. Reports
   `"Overall {overall}/100 — {verdict}"` (`publishable` if `overall >= 75`, else
   `promising but needs work`) plus `"AP-style check: {ap_score}/100 with N
   note(s)."`

Regardless of path, the `ap_style` category score is the deterministic
`ap["ap_score"]`, and the weighted formula governs the overall whenever the model
does not supply a valid positive integer.
