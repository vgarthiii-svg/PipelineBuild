# Prompt Templates — The Modular Prompt System

Source of truth: `backend/app/ai/prompts.py`

The Content Creator Engine builds every model prompt out of small, composable
**modules**. Each module is a self-contained block of context that injects one
slice of the user's inputs (brand, platform, audience, research, etc.). The task
builders (`build_generation_prompt`, `build_scoring_prompt`, …) assemble only the
modules they need into a single prompt.

> **Guiding principle: never generic — always grounded in inputs.**
> Every module pulls from the supplied brand profile, platform rules, audience,
> and current research. The generator system prompt is explicit: *"You never
> produce generic filler. You ground every choice in the supplied brand profile,
> platform rules, audience, and current research. You never plagiarize viral
> content — you learn from its patterns and create something original."*

---

## System prompts

Three role-defining system strings set the model's persona per task.

| Constant | Used by | Role |
| --- | --- | --- |
| `SYSTEM_GENERATOR` | generation, revision, repurpose | Senior content strategist + conversion copywriter who thinks like a journalist. Writes original, platform-native content; grounds every choice in inputs; learns from viral *patterns* without plagiarizing. |
| `SYSTEM_SCORER` | scoring | Rigorous content editor and growth analyst. Scores honestly, "not a cheerleader; a 100 is rare." Penalizes hype, vagueness, weak hooks, unsupported claims. |
| `SYSTEM_RESEARCHER` | research | Market and content researcher. Identifies trends, patterns, hooks, pain points, SEO opportunities, gaps. Synthesizes patterns rather than copying; always cites sources and notes recency/confidence. |

---

## Context modules

Each function returns a single text block (or `""` when not applicable). Empty
modules are filtered out at assembly time.

### `brand_module(brand)`
Injects the brand profile. If `brand` is falsy it returns a neutral fallback:
`"BRAND CONTEXT: (none provided — keep voice neutral-professional)."`

Otherwise it emits a `BRAND CONTEXT:` block with any populated fields among:
Company, Website, Industry, Audience, Products/Services, Brand voice,
Differentiators, Proof points, Offers, Preferred CTA language, Approved
boilerplate, Compliance rules. It additionally lists, when present:
- `Words to USE:` (joined `words_to_use`)
- `Words to AVOID:` (joined `words_to_avoid`)
- `Competitors:` (joined `competitors`)

### `platform_module(rule, platform, content_type)`
Injects the platform/content-type best-practices rule. With no rule it returns a
one-liner telling the model to follow current best practices for
`{platform}/{content_type}`. With a rule it emits:
- A `PLATFORM RULES — {label} ({platform}/{content_type}):` header
- `Required structure (in order):` joined with ` -> ` (from `rule["structure"]`)
- `Best practices:` as a bulleted list (from `rule["best_practices"]`)
- `Constraints:` (from `rule["constraints"]`)

Rules come from `engines/platform_rules.py` (`PLATFORM_RULE_SEED` / `find_rule`).

### `audience_module(project)`
Always emits an `AUDIENCE & GOAL:` block, each line defaulting if absent:
Target audience (`general professional`), Business goal (`awareness`), Funnel
stage (`TOFU`), Desired outcome (`engagement`), Geographic market (`global`),
Tone (`professional`).

### `research_module(brief)`
Injects the research brief so the draft is grounded in current findings. With no
brief: `"RESEARCH: (not yet run — rely on best practices)."` With a brief it
emits `CURRENT RESEARCH FINDINGS (ground the content in these):` and, for any
non-empty value, the first 5 of: `trends`, `high_performing_patterns`,
`common_hooks`, `audience_pain_points`, `content_gaps`. It also adds
`recommended_angle`, `recommended_hook`, and the first 10 `keywords` when present.

### `AP_STYLE_MODULE` (constant)
A fixed block of AP-style / journalistic principles the model must apply
(explicitly *without quoting any stylebook*): clarity/concision/active voice;
spell out one–nine, figures for 10+; sentence-case headlines, no ALL CAPS;
attribute claims, avoid weasel words and unsupported superlatives; cut hype,
fluff, jargon; consistent serial-comma per brand preference; consistent
date/time formatting; no exaggerated/unverifiable claims without a cited proof
point.

### `seo_module(project)`
Returns `""` (skipped) when there are no `keywords` **and** the content type is
not one of `blog`, `website`, `landing`, `brief`. Otherwise emits `SEO RULES:`
covering: keywords to work in naturally (or `(infer 3-5)`), match search intent /
answer early, SEO title (<=60 chars) + meta description (<=155 chars) when
relevant, suggest H1/H2/H3 + internal links + FAQ, never keyword-stuff.

### `cta_module(project, brand)`
Always emits `CTA RULES:` — Primary CTA (`project["cta"]` or
`drive the desired outcome`), Preferred CTA language (from the brand, or natural
benefit-led phrasing), one primary CTA, explicit benefit, offer 2–3 CTA variants.

### `compliance_module(project, brand)`
Uses `project["compliance"]`, else `brand["compliance_rules"]`. With nothing set:
`"COMPLIANCE: standard — no unverifiable claims, no guarantees of results."`
Otherwise: `"COMPLIANCE CONSTRAINTS (must honor): {notes}"`.

---

## Task builders

### `build_generation_prompt(project, brand, rule, brief)`
Assembles the full draft prompt. It composes the modules **in this exact order**:

1. `brand_module(brand)`
2. `platform_module(rule, platform, content_type)`
3. `audience_module(project)`
4. `research_module(brief)`
5. `AP_STYLE_MODULE`
6. `seo_module(project)`
7. `cta_module(project, brand)`
8. `compliance_module(project, brand)`

Non-empty modules are joined with blank lines into `context`, then a `TASK:`
block is appended (content type, platform, objective, offer, length) followed by
the **JSON output contract** (see below). The closing instruction reinforces the
principle: *"Make it original, specific to the inputs, and free of generic filler."*

### `build_research_prompt(project, brand)`
Begins with `SYSTEM_RESEARCHER`, states the topic (objective → offer →
content_type fallback) plus platform, content_type, industry, audience,
competitors, geo_market, then requests a research-brief JSON object and ends with
*"Synthesize PATTERNS — do not copy any specific post. Note recency and confidence."*

### `build_scoring_prompt(draft_body, project, brand, categories, ap_findings)`
Begins with `SYSTEM_SCORER`, lists every scoring category as
`- {key}: {label} — {desc}`, injects context (platform, type, audience, goal,
brand voice). If `ap_findings` are supplied it appends a note listing what the
deterministic AP checker already flagged (`rule (severity)`, up to 10). Then it
embeds the content and the scoring JSON contract, instructing *"Use the exact
category keys provided."*

### `build_revision_prompt(body, action, instruction, project, brand)`
`SYSTEM_GENERATOR` + `brand_module` (+ `AP_STYLE_MODULE` only when
`action == "ap_style"`). Maps a fixed set of `action` keys (`rewrite`, `shorten`,
`expand`, `professional`, `conversational`, `direct`, `add_stats`, `add_cta`,
`remove_fluff`, `ap_style`, `variations`) to directives; unknown actions fall
back to the free-form `instruction`. Returns **plain text** (variations separated
by a `---` line) — not JSON.

### `build_repurpose_prompt(source_body, source_type, targets, project, brand)`
`SYSTEM_GENERATOR` + `brand_module`, instructs transforming the source into each
target format (ready-to-publish, not a summary), and returns
`{"outputs": [{"format", "content"}, ...]}`.

---

## JSON output contracts

The provider's `complete_json` appends *"Respond with a single valid JSON object
and nothing else."* and defensively extracts the object (strips code fences,
falls back to outermost braces). The expected shapes:

**Generation** — a single JSON object with:
`title`, `body`, `structured` (`{"sections": [{"name","text"}]}`),
`headline_options` (3–5), `cta_options` (2–3), `hook_options` (2–3),
`rationale`, `posting_guidance`, `repurposing_suggestions` (3–5),
`recommended_edits` (`[{"area","suggestion"}]`).

**Research** — keys: `trends`, `high_performing_patterns`,
`competitor_observations`, `audience_pain_points`, `content_gaps`,
`common_hooks`, `keywords`, `related_questions`, `search_intent`,
`recommended_angle`, `recommended_hook`, `recommended_cta`, `risks`,
`market_context`, and `sources` (`[{"title","url","snippet","source_type"}]`).

**Scoring** —
```json
{"overall": <weighted 0-100 int>,
 "summary": "<2-3 sentence verdict>",
 "categories": { "<key>": {"score": int, "working": str, "weak": str,
                           "improvements": [str, ...]} } }
```

**Repurpose** — `{"outputs": [{"format": str, "content": str}, ...]}`.

**Revision** — plain text (not JSON); variations split by a `---` line.

---

## Example assembled generation prompt (skeleton)

```
BRAND CONTEXT:
- Company: Acme Co
- Industry: B2B SaaS
- Brand voice: confident, plain-spoken
- Words to USE: outcomes, proof
- Words to AVOID: synergy, world-class
- Competitors: Globex, Initech

PLATFORM RULES — LinkedIn Post (LinkedIn/linkedin):
Required structure (in order): Hook (line 1) -> Context -> Insight/Story -> Takeaways -> Closing thought / CTA
Best practices:
  - Open with a strong, scroll-stopping hook in the first line
  - Use short paragraphs and white space
  - ...
Constraints: {'max_chars': 3000, 'ideal_chars': 1300, 'hashtags': '1-3', ...}

AUDIENCE & GOAL:
- Target audience: RevOps leaders
- Business goal: pipeline
- Funnel stage: MOFU
- Desired outcome: book a call
- Geographic market: North America
- Tone: confident

CURRENT RESEARCH FINDINGS (ground the content in these):
- Trends: Short opinionated takes outperform long explainers; ...
- High Performing Patterns: Hook + 3 bullets + 1 CTA; ...
- Common Hooks: Most people get X wrong; ...
- Recommended angle: Lead with a contrarian, outcome-first take.
- Recommended hook: Most advice about X is backwards...
- Keywords: revops, pipeline efficiency, ...

AP-STYLE / JOURNALISTIC PRINCIPLES (apply, do not quote any stylebook):
- Prefer clarity, concision, and active voice.
- ...

SEO RULES:
- Primary/secondary keywords to work in naturally: revops, pipeline efficiency
- ...

CTA RULES:
- Primary CTA: Book a 20-minute audit
- Preferred CTA language: ...
- One primary CTA. Make the benefit of acting explicit. Offer 2-3 CTA variants.

COMPLIANCE CONSTRAINTS (must honor): No ROI guarantees; cite any statistic.

TASK: Generate a first-draft linkedin post for LinkedIn.
objective: ...
offer: ...
length: medium

Return a single JSON object with these keys:
- "title": ...
- "body": ...
- ... (full generation contract)

Make it original, specific to the inputs, and free of generic filler.
```

(System message for the call above is `SYSTEM_GENERATOR`.)
