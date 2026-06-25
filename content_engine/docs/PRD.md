# Product Requirements Document — Content Creator Engine

> A production-grade **marketing command center**, not a basic AI writing tool.
> Select a platform and content type, feed in your business context, run live
> research on what's working, then **research → generate → score → revise →
> repurpose → organize** high-quality content that follows platform best
> practices, AP-style journalistic principles, brand voice, SEO rules, and
> conversion strategy.

This PRD describes the product as actually implemented in this repository. It is
deliberately scoped to what the code does; planned work lives under *Roadmap*.

---

## 1. Vision & Goal

Marketers do not need another blank-box "write me a post" tool. They need a
system that *thinks like a strategist and a journalist* — one that grounds every
piece of content in the brand, the platform, the audience, current research, and
a conversion goal, then holds the output to an honest quality bar before it ships.

**Goal:** Take a user from a business objective to a publishable, on-brand,
platform-native, conversion-oriented piece of content — with a defensible quality
score and a clear path to repurpose and schedule it — in a single guided workflow
that runs end-to-end **with or without an AI API key**.

A deterministic **mock provider** guarantees the full workflow is always runnable,
testable, and demoable offline; a real Anthropic key unlocks live generation and
research quality.

---

## 2. Target Users

| User | What they need from the engine |
|------|--------------------------------|
| **Independent consultant** | Produce credible thought leadership and LinkedIn presence fast, in their own voice, without a content team. |
| **Marketing agency** | Run many brands/clients in parallel via reusable **brand profiles**; keep voice, compliance, and quality consistent across deliverables. |
| **In-house marketing team** | A shared pipeline (idea → published), brand-voice enforcement, scoring, calendar, and a searchable library. |
| **Founder** | Punch above weight: research-backed posts, launch copy, and landing pages without hiring. |
| **Business development / sales** | Sales-enablement copy, outreach, and announcements grounded in proof points and a clear ask. |

All users share the same need: **specific, grounded, on-brand content** — never
generic filler — plus the discipline of scoring, revision, and organization.

---

## 3. Supported Content Types (13)

Defined in `backend/app/engines/platform_rules.py` (`CONTENT_TYPES`). Each type
carries its own required structure, best practices, and constraints used by the
prompt builder and the scorer.

| # | Key | Content type |
|---|-----|--------------|
| 1 | `linkedin` | LinkedIn post |
| 2 | `email` | Email marketing campaign |
| 3 | `website` | Website copy |
| 4 | `landing` | Landing page |
| 5 | `blog` | Blog post (SEO) |
| 6 | `newsletter` | Newsletter content |
| 7 | `social` | Social media post / thread |
| 8 | `ad` | Short-form ad copy |
| 9 | `thought_leadership` | Long-form thought leadership |
| 10 | `sales` | Sales enablement copy |
| 11 | `press` | Press-release-style announcement |
| 12 | `brief` | SEO content brief |
| 13 | `repurpose` | Repurposed content |

**Platforms** offered alongside content types (`PLATFORMS`): LinkedIn, Email,
Website, Blog, X/Twitter, Instagram, Facebook, TikTok, YouTube, Newsletter,
Press, Generic.

---

## 4. User-Selectable Inputs

Captured by the New Content wizard (`frontend/js/app.js`), persisted on the
`content_projects` table (`backend/app/models.py`), and fed into every prompt
module (`backend/app/ai/prompts.py`). Dropdown option sets are served from
`/api/meta` (`backend/app/routers/meta.py`).

| Input | Field | Source of options |
|-------|-------|-------------------|
| Platform | `platform` | `PLATFORMS` |
| Content type | `content_type` | `CONTENT_TYPES` |
| Target audience | `target_audience` | free text |
| Business goal | `business_goal` | Brand awareness, Lead generation, Demand generation, Engagement, Conversions/Sales, Retention, Thought leadership, Recruiting |
| Funnel stage | `funnel_stage` | Awareness (TOFU), Consideration (MOFU), Decision (BOFU), Retention, Advocacy |
| Tone | `tone` | Professional, Conversational, Authoritative, Bold, Friendly, Witty, Empathetic, Inspirational, Data-driven, Minimal |
| Brand voice | via Brand profile (`brand_id` → `brand_voice`, words to use/avoid, etc.) | brand profile |
| CTA | `cta` | free text (+ preferred CTA language from brand) |
| Length | `length` | short, medium, long |
| Keywords | `keywords` (list) | free text, comma-separated |
| Offer / service | `offer` | free text |
| Industry | `industry` | free text |
| Competitors | `competitors` (list) | free text, comma-separated |
| Geographic market | `geo_market` | free text |
| Compliance considerations | `compliance` | free text |
| Desired outcome | `desired_outcome` | free text |
| Objective | `objective` | free text (what the content must achieve) |
| Title / Campaign | `title`, `campaign` | free text |

The wizard groups these into four steps: **Brand & platform → Content & goal →
Audience & product → Voice & CTA.**

---

## 5. Core Features

### 5.1 Research engine (`engines/research.py`)
Produces a **timestamped, source-cited research brief before drafting**. Output
fields (persisted on `research_briefs` / `research_sources`): trends,
high-performing patterns, competitor observations, audience pain points, content
gaps, common hooks, keywords, related questions, search intent, recommended
angle / hook / CTA, risks, market context, plus a list of sources
(title/url/snippet/source_type/retrieved_at) and the `model_used`.
It **synthesizes patterns** and never copies specific viral content. With a real
key + `RESEARCH_PROVIDER=anthropic_web` it grounds the brief in model knowledge;
otherwise it returns a clearly-labeled *synthesized* brief.

### 5.2 AP-style layer (`engines/ap_style.py`)
A practical, **rule-based** journalistic checker (no copyrighted stylebook text).
Detects hype/fluff words, weasel/filler words, passive voice, exclamation
overuse, ALL-CAPS, numeral inconsistencies (spell out 1–9), overlong sentences,
and unsupported superlative claims. Returns findings
(`rule, category, severity, message, matches, count`) and a **deterministic
0–100 `ap_score`**. Users add **custom editorial rules** (regex/phrase/heuristic)
stored as `style_guide_rules`, merged in at check time. Exposed both inside
scoring and as a standalone checker (`POST /api/settings/ap-check`).

### 5.3 Platform best-practices engine (`engines/platform_rules.py`)
Per platform/content-type **rules-as-data**: ordered required structure, best
practices, and constraints (length, hashtags, emoji policy, CTA count, SEO
limits, etc.). Seeded on startup into `platform_rules` and **editable in
Settings**, so the rules that drive generation and scoring can be tuned without
code changes.

### 5.4 14-category scoring engine (`engines/scoring.py`)
Every draft is scored **1–100 overall** plus 14 weighted categories, each with
*what's working*, *what's weak*, and concrete *improvements*.

| Category | Weight | Category | Weight |
|----------|:------:|----------|:------:|
| Platform fit | 1.2 | Brand voice alignment | 1.0 |
| Audience fit | 1.1 | Originality | 1.0 |
| Hook strength | 1.2 | Readability | 1.0 |
| Clarity | 1.1 | CTA strength | 1.1 |
| Conversion strength | 1.2 | Research support | 0.9 |
| SEO strength | 0.9 | Compliance risk* | 1.0 |
| AP-style alignment** | 1.0 | Engagement potential | 1.1 |

\* Higher = lower risk. \*\* The AP-style category score is **forced to the
deterministic AP checker's `ap_score`** so it is auditable and reproducible even
without an API key. The overall is a weighted average (model-provided when valid,
otherwise computed from category scores).

### 5.5 Draft generation & editor (`engines/generation.py`, `routers/drafts.py`)
Generates a structured first draft (title, body, platform-mirrored sections,
3–5 headline options, 2–3 CTA options, 2–3 hook options, rationale, posting
guidance, repurposing suggestions, recommended edits). The editor supports named
revision actions, each logged to `revision_history` (before/after):
**rewrite, shorten, expand, more professional, more conversational, more direct,
add statistics, add/strengthen CTA, remove fluff, convert to AP style, generate
variations.** Drafts are versioned per project.

### 5.6 Repurposing engine (`engines/repurpose.py`)
Transforms one piece into many target formats (LinkedIn post, email newsletter,
short social posts, landing-page section, sales email, website FAQ, short video
script, X/Twitter thread, executive summary, …), each adapted to its own best
practices — not a summary.

### 5.7 Content library (`routers/library.py`)
Searchable, filterable view of every draft joined to its project: filter by
query, platform, content type, and status; shows latest score, version, final
flag, tags, audience, CTA, and timestamps.

### 5.8 Calendar (`routers/calendar.py`)
Schedule entries (title, platform, scheduled date, status, notes) linked to
projects/drafts; CRUD for planning the publishing pipeline.

### 5.9 Brand profiles (`routers/brands.py`)
Reusable voice and context: company, website, industry, audience, products,
**brand voice**, **words to use / avoid**, **competitors**, differentiators,
**proof points**, **offers**, **compliance rules**, preferred CTA language,
style preferences, approved boilerplate, and team notes. Selecting a brand in
the wizard injects all of it into the prompts.

### 5.10 Exports (`engines/export.py`)
Markdown, HTML, plain text, CSV, and DOCX (DOCX via `python-docx`, with a text
fallback; PDF via client print of the HTML payload). Each export is logged to
`export_history`.

### 5.11 Status pipeline
Project status flows: **idea → researching → drafted → needs_review → approved →
scheduled → published → archived** (advanced automatically by research/generate/
finalize actions and adjustable by the user).

---

## 6. The 15-Step Content Workflow

The product is organized around a single, opinionated workflow (surfaced on the
Dashboard and enacted across the wizard + project workspace):

```
 1. Brand profile      → choose/create reusable voice & context
 2. Platform           → where it will be published
 3. Content type       → one of the 13 supported types
 4. Objective          → what this content must achieve
 5. Audience           → who it's for (+ funnel stage, geo)
 6. Product / offer    → what is being promoted
 7. Tone               → voice and register
 8. CTA                → the action to drive
 9. Research           → run the research engine (brief + sources)
10. Strategy brief     → review recommended angle/hook/keywords
11. Draft              → generate the structured first draft
12. Score              → 14-category scorecard (overall 1–100)
13. Improve            → revise via editor actions; AP-style pass
14. Export             → Markdown / HTML / text / CSV / DOCX (PDF via print)
15. Library            → save, tag, search, schedule on the calendar
```

Steps 1–8 are the wizard inputs; steps 9–15 are the project workspace and the
library/calendar.

---

## 7. Content-Output Requirements

Generated content must:

- **Follow the platform's required structure** and constraints for the chosen
  content type (e.g., LinkedIn hook-first with sparing emoji; email with 3
  subject options + one primary CTA; blog with SEO title/meta + H1/H2/H3 + FAQ).
- **Be grounded in the inputs** — brand voice, audience, funnel stage, research
  findings, keywords, offer, compliance — never generic filler.
- **Honor AP-style/journalistic principles**: clarity, active voice, numerals
  policy, no hype, attributed claims.
- **Honor SEO rules** where relevant (keyword/intent coverage, SEO title ≤60
  chars, meta description ≤155 chars, heading hierarchy, no keyword stuffing).
- **Drive one primary CTA** with explicit benefit, plus 2–3 CTA variants.
- **Respect compliance constraints** (no unverifiable claims/guarantees).
- **Ship with options**: alternative headlines, hooks, and CTAs, a performance
  rationale, posting guidance, and repurposing suggestions.
- **Be original** — synthesize patterns from research, never copy viral content.

---

## 8. Non-Goals

- **Not an autonomous publisher.** The app does not post to social networks, send
  emails, or publish to a CMS. Publishing/export-to-platform are roadmap seams.
- **Not a real-time web crawler.** Research synthesizes patterns from model
  knowledge / web tooling; it does not scrape or republish third-party content.
- **Not a stylebook reproduction.** The AP-style layer encodes general
  journalistic principles; it does not contain copyrighted stylebook text.
- **Not a multi-tenant SaaS out of the box.** Default is single-user dev mode;
  real auth is an integration seam, not a shipped feature.
- **Not an image/video generator.** Output is text content and structure.
- **No guaranteed-results or performance claims** in generated copy.

---

## 9. Success Metrics

- **Quality:** median draft **overall score ≥ 80**; AP-style score ≥ 80 ("passes").
- **Throughput:** objective → publishable draft in one guided session.
- **Grounding:** every shipped piece traces to brand + platform rules + a research
  brief with at least one cited/synthesized source.
- **Reuse:** brand profiles and repurposing reduce time-to-Nth-asset.
- **Pipeline health:** projects progress through statuses; library/calendar are
  actively used to organize and schedule.
- **Always-on:** full workflow completes with zero external keys (mock mode),
  verified by the end-to-end test suite.

---

## 10. Roadmap

Near-term seams already designed for (see `ARCHITECTURE.md` → *Integration seams*):

- **Auth & multi-tenant** — drop-in Clerk/Supabase/Auth0 via `deps.get_current_user`.
- **Postgres/Supabase** — set `DATABASE_URL`; models are portable today.
- **Publish/export targets** — Google Drive & Gmail (drafts/exports), Mailchimp
  (email campaigns), HubSpot (CRM/marketing), WordPress (blog/website) as
  export/publish destinations.
- **Live research provider** — richer web-grounded sourcing.
- **Additional AI providers** — the `AIProvider` interface supports adding
  vendors without touching engines.
- **Analytics loop** — feed published-content performance back into scoring.
