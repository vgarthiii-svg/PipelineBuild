# Testing Plan — Content Creator Engine

This document describes the test strategy for the Content Creator Engine: the
existing automated tests, why they are deterministic, a manual QA checklist, and
recommended future coverage.

---

## Goals

- The full content workflow must be exercisable **without any API key**, so tests
  can run in CI and offline.
- Core engines (AP-style, generation, research, scoring, repurpose) must be
  unit-tested in isolation.
- The HTTP surface must be tested end-to-end across the real workflow a user
  follows in the UI: brand → project → research → generate → score → revise →
  repurpose → export → library → finalize.

---

## How tests stay deterministic — the Mock provider

Every engine takes an `AIProvider` instance rather than calling a model directly.
The tests inject `MockProvider` (`app/ai/provider.py`), a dependency-free,
template-driven provider. Its `complete_json` branches on lightweight markers in
the prompt (e.g. "scorecard", "research brief", "repurpose") and returns
structured, well-formed output derived from the prompt. Because the output is
deterministic and contains no real model calls:

- tests produce stable, repeatable results;
- no network, no API key, and no cost;
- the entire generate → score → revise → repurpose pipeline runs offline.

The API tests force this mode via environment variables set **before** importing
the app:

```python
os.environ["DATABASE_URL"] = f"sqlite:///{tmpdir}/test.db"  # throwaway DB
os.environ["AI_PROVIDER"] = "mock"
os.environ["SINGLE_USER_MODE"] = "1"
```

The throwaway SQLite file isolates each run; `SINGLE_USER_MODE=1` auto-provisions
the default user so no auth header is required.

---

## Running the tests

From the backend directory:

```bash
cd content_engine/backend
AI_PROVIDER=mock python -m pytest tests/ -q
```

This runs the full suite (engine unit tests + end-to-end API tests) with the
deterministic mock provider. (`test_api.py` also sets `AI_PROVIDER=mock` itself,
but passing it explicitly keeps the engine tests in mock mode too.)

You can also run a single file directly:

```bash
python -m pytest tests/test_engines.py -v
python tests/test_api.py     # has a __main__ that invokes pytest -v
```

---

## Existing automated coverage

### Unit tests — `tests/test_engines.py`

Each test instantiates `MockProvider()` directly and calls one engine with a
representative `PROJECT` and `BRAND` dict.

| Test | Engine | Asserts |
|------|--------|---------|
| `test_ap_style_flags_hype_and_scores` | `ap_style.check` | Hype-laden text scores < 100 and produces a `hype` category finding. |
| `test_ap_style_clean_text_scores_high` | `ap_style.check` | Clean, plain text scores ≥ 80. |
| `test_generate_draft_returns_full_structure` | `generation.generate_draft` | Returns a non-empty `body`, ≥ 1 `headline_options`, and a `model_used` field. |
| `test_research_brief_has_sources_and_timestamp` | `research.run_research` | Brief includes `sources`, a `generated_at` timestamp, and `keywords`. |
| `test_scoring_returns_14_categories` | `scoring.score_draft` | Category keys exactly match `SCORE_CATEGORIES` (14), `overall` is 0–100, and the `ap_style` category score equals the deterministic AP checker's `ap_score` (auditable). |
| `test_repurpose_produces_outputs` | `repurpose.repurpose` | Produces ≥ 2 outputs, each with `format` and `content`. |

These pin the *contract* of each engine — shape of output, key invariants, and
the AP-style ↔ scoring linkage — independent of model quality.

### End-to-end API tests — `tests/test_api.py`

Uses FastAPI's `TestClient` entered as a context manager so the **lifespan
handler runs** (table creation + seed of platform/style rules) against the
throwaway SQLite DB.

| Test | Coverage |
|------|----------|
| `test_health` | `GET /api/health` returns 200 and `status == "ok"`. |
| `test_meta_lists_content_types` | `GET /api/meta` exposes 13 content types and 14 score categories (drives the wizard + scorecard UI). |
| `test_full_workflow` | The complete pipeline in one test (see below). |
| `test_ap_check_endpoint` | `POST /api/settings/ap-check` flags hype, scoring < 100. |

**`test_full_workflow`** walks the exact path a user takes in the SPA:

1. **Brand** — `POST /api/brands` → 201, capture `brand_id`.
2. **Project** — `POST /api/projects` (linked to the brand) → 201, capture `pid`.
3. **Research** — `POST /api/projects/{pid}/research` → 200, brief has `keywords`.
4. **Generate** — `POST /api/projects/{pid}/generate` → 200, draft has a `body`; capture `did`.
5. **Score** — `POST /api/drafts/{did}/score` → 200, `overall` 0–100, 14 categories.
6. **Revise** — `POST /api/drafts/{did}/revise` `{"action":"shorten"}` → 200.
7. **Repurpose** — `POST /api/drafts/{did}/repurpose` `{"targets":["Email newsletter"]}` → 200, has `outputs`.
8. **Export** — `GET /api/drafts/{did}/export/markdown` → 200, body contains `#`.
9. **Library** — `GET /api/library` → 200, `count >= 1`.
10. **Finalize** — `POST /api/drafts/{did}/finalize` → 200, `is_final == true`.

This single test gives broad integration coverage: routing, DB persistence,
schema validation, the provider seam, and cross-engine wiring.

---

## Manual QA checklist

Run with `bash run.sh` (mock mode) and again with a real `ANTHROPIC_API_KEY` for
quality verification.

**Shell & navigation**
- [ ] Sidebar nav highlights the active route; breadcrumb updates per view.
- [ ] AI status pill reads "mock" without a key, "live" with one.
- [ ] Toast appears/auto-dismisses; modal closes on click-outside.

**Dashboard**
- [ ] Stat cards show correct counts; Avg Score is "—" when nothing is scored.
- [ ] Pipeline-by-status counts match library; recent projects link to workspace.

**New Content wizard**
- [ ] Title is required; submit creates a project and opens the workspace.
- [ ] Keywords/competitors split on commas; "ad-hoc" brand sends null `brand_id`.

**Project workspace**
- [ ] Run research populates the brief panel with model + timestamp; re-run relabels button.
- [ ] Generate draft fills editor (title, body, options, rationale, guidance).
- [ ] Each editor action (Rewrite … Generate variations) updates the body.
- [ ] Save persists; Finalize approves and returns to workspace.
- [ ] Score draft renders the ring + 14 category bars; existing score auto-loads.
- [ ] AP-style category score matches the Style Guide checker for the same text.
- [ ] Repurpose modal lists formatted outputs with working copy buttons.
- [ ] Export links download Markdown/HTML/Text/CSV/DOCX.

**Library**
- [ ] Search + platform/status filters narrow the table; rows open the project.
- [ ] Final items show ✅; scores are colored; version/created render correctly.

**Brands**
- [ ] Create, edit, and delete a brand; comma fields round-trip as arrays.

**Calendar**
- [ ] Schedule an entry (date required); it appears in the list; remove works.

**Style Guide**
- [ ] AP check returns score/verdict/findings; add a custom phrase + regex rule;
      toggle on/off; delete non-system rules (system rules not deletable).

**Settings**
- [ ] Health reflects provider mode; change + save default export format;
      add/delete snippets; platform rules list renders with structure steps.

---

## Recommended future tests

- **Authentication / multi-user** — exercise `SINGLE_USER_MODE=0` with a real
  auth dependency: 401 without credentials, per-user data isolation, and the
  `deps.get_current_user` seam.
- **PostgreSQL / Supabase** — run the suite against `DATABASE_URL=postgresql+...`
  to catch SQLite-vs-Postgres differences (types, migrations, constraints);
  ideally in CI with a Postgres service container.
- **Live-provider contract tests** — opt-in tests (gated on a key) that hit the
  real `AnthropicProvider`/web research and assert the JSON *shape* the engines
  expect, so model/SDK changes are caught without asserting exact wording.
- **Frontend E2E** — Playwright/Cypress driving the SPA through the full wizard →
  workspace → export flow in a browser, covering routing, modals, copy-to-clipboard,
  and download links.
- **Engine edge cases** — empty/very long drafts, missing brand, non-ASCII, every
  editor action and every export format, and AP-style regex rule validation.
- **Error-path / negative tests** — 404s for missing ids, validation 422s, and
  graceful handling when the provider returns malformed JSON (the scoring
  fallbacks).
