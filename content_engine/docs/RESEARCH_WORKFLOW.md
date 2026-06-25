# Research Workflow

Source of truth: `backend/app/engines/research.py`, `backend/app/ai/prompts.py`
(`build_research_prompt`, `SYSTEM_RESEARCHER`), and the research branch of
`backend/app/ai/provider.py`.

The research engine produces a **timestamped, source-cited research brief BEFORE
drafting**. The brief grounds generation so output is never generic — it is
anchored in current trends, patterns, hooks, SEO opportunities, and market
context relevant to the project.

> **Core rule: synthesize patterns, never copy viral content.**
> The researcher system prompt and `build_research_prompt` both instruct the
> model to *"Synthesize PATTERNS — do not copy any specific post."* The engine's
> module docstring reinforces it: *"The engine NEVER copies viral content — the
> prompt instructs pattern synthesis."*

---

## Entry point

```python
run_research(*, provider: AIProvider, project: dict, brand: dict | None) -> dict
```

Steps:
1. Build the prompt with `build_research_prompt(project=project, brand=brand)`.
2. Call `provider.complete_json(SYSTEM_RESEARCHER, prompt)`.
3. If the result is not a dict or has `_parse_error`, treat it as empty `{}`
   (graceful degradation — the workflow still completes).
4. Normalize list fields, normalize/timestamp sources, set `model_used`, stamp
   `generated_at`, and return the full brief.

## Inputs

From `project` (with `brand` as fallback for some fields), `build_research_prompt`
uses:
- **topic** — `objective` → `offer` → `content_type` (first non-empty)
- **platform**, **content_type**
- **industry** — `project["industry"]` or `brand["industry"]`
- **audience** — `project["target_audience"]`
- **competitors** — `project["competitors"]` or `brand["competitors"]` (joined)
- **geo_market**

---

## Provider strategy

Research reuses the chat provider (`get_research_provider()` returns
`get_ai_provider()`); the research engine itself owns the web-tooling intent.

- **Live (`anthropic_web`)** — when a real API key is configured and
  `RESEARCH_PROVIDER=anthropic_web` (`settings.research_enabled`), the model is
  asked to ground the brief in current knowledge and surface candidate sources.
  `model_used` is the provider name (e.g. `anthropic`).
- **Mock / synthesized** — with no key (or research disabled), `MockProvider`
  returns a structured, clearly-labeled synthesized brief
  (`_mock_research`) so the workflow always completes offline. `model_used` is
  suffixed `" (synthesized)"`.

The mock branch is selected in `MockProvider.complete_json` when the prompt
contains `"research brief"` or `"research the following"` (markers emitted by the
research prompt template).

---

## Brief fields produced

`run_research` returns a normalized dict with every field guaranteed present.
List fields are coerced to `[]` if missing/wrong-type via the local `lst()`
helper; string fields default to `""`.

| Field | Type | Meaning |
| --- | --- | --- |
| `trends` | list | Current, relevant trends for the topic/platform. |
| `high_performing_patterns` | list | Structural patterns that perform well. |
| `competitor_observations` | list | Themes/gaps seen in competitor content. |
| `audience_pain_points` | list | Problems the audience actually feels. |
| `content_gaps` | list | Under-served angles to exploit. |
| `common_hooks` | list | Hook formulas that earn attention. |
| `keywords` | list | SEO/keyword opportunities. |
| `related_questions` | list | Questions the audience asks (intent coverage). |
| `search_intent` | str | Informational/commercial/etc. intent summary. |
| `recommended_angle` | str | The angle the draft should take. |
| `recommended_hook` | str | A specific recommended opening hook. |
| `recommended_cta` | str | A recommended call to action. |
| `risks` | str | Pitfalls to avoid (e.g. unsupported superlatives). |
| `market_context` | str | Broader buyer/market framing. |
| `model_used` | str | Provider name; `" (synthesized)"` when not live. |
| `generated_at` | datetime | UTC timestamp of the run. |
| `sources` | list | Cited sources (see below). |

---

## Timestamping + source citation

- `generated_at` is set once to `datetime.now(timezone.utc)` and reused for all
  source `retrieved_at` stamps — the whole brief is consistently timestamped.
- Each source is normalized to:
  `{title, url, snippet, source_type, retrieved_at}`. Defaults: `title="Source"`,
  `url=""`, `snippet=""`, `source_type="synthesized"`,
  `retrieved_at=now.isoformat()`.
- Non-dict entries in `sources` are skipped.
- If no usable sources are returned, a single explicit fallback source is added:
  *"Synthesized best-practice patterns"* with the snippet *"No live web sources
  available; brief synthesized from platform best practices and model knowledge."*
  (`source_type="synthesized"`). This keeps the citation contract honest even
  offline — synthesized content is always labeled as such.

The research prompt asks for `sources` as
`[{"title","url","snippet","source_type"}]` and instructs the model to *"always
cite sources and note the recency and confidence of your findings."*

---

## How the brief feeds generation

The returned brief is passed as the `brief` argument to
`build_generation_prompt`, where `research_module(brief)` injects a
`CURRENT RESEARCH FINDINGS (ground the content in these):` block:
- The first 5 items each of `trends`, `high_performing_patterns`,
  `common_hooks`, `audience_pain_points`, `content_gaps`.
- `recommended_angle`, `recommended_hook`, and the first 10 `keywords`.

This is what makes generated drafts grounded rather than generic — the model is
told the live angle, hook, and patterns to build on, while the
synthesize-don't-copy rule prevents replicating any specific viral post.
