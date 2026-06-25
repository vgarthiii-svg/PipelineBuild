# API Routes — Content Creator Engine

FastAPI application defined in `backend/app/main.py` (title "Content Creator
Engine", version 1.0.0). All API routes are namespaced under `/api`. The SPA
frontend is served from `/` and `/static` when the frontend directory exists.

## Authentication convention

Auth is handled by `get_current_user` in `backend/app/deps.py`:

- Requests identify the user with the **`X-User-Email`** request header.
- In **single-user mode** (default), if the header is absent the configured
  `default_user_email` is used, and the user is auto-provisioned in the database
  if not already present.
- If multi-user mode is enabled and no `X-User-Email` is supplied, the request
  is rejected with `401 Authentication required` / `401 Unknown user`.
- There is no JWT/session today; the auth seam is designed to be swapped for
  Clerk/Supabase/Auth0 by replacing `get_current_user` alone.

Send the header on every request, e.g.:

```
X-User-Email: vgarthiii@gmail.com
```

## Health (unprefixed)

| Method | Path          | Purpose             | Response                                                              |
|--------|---------------|---------------------|----------------------------------------------------------------------|
| GET    | `/api/health` | Liveness + feature flags | `{status, ai_enabled, research_enabled, ai_provider}` |

`GET /` returns the SPA `index.html` (only when the frontend dir is present).

---

## Core workflow call sequence

The primary end-to-end flow ties the project and draft routers together:

1. `POST /api/projects` — create a project (wizard inputs).
2. `POST /api/projects/{project_id}/research` — generate a research brief.
3. `POST /api/projects/{project_id}/generate` — generate a draft (uses brand,
   platform rule, and latest brief). Returns a `DraftOut` with an `id`.
4. `POST /api/drafts/{draft_id}/score` — score the draft.
5. `POST /api/drafts/{draft_id}/revise` — apply an editor action to the body.
6. `POST /api/drafts/{draft_id}/repurpose` — adapt the draft for other platforms.
7. `GET  /api/drafts/{draft_id}/export/{fmt}` — download the draft.

Optional: `POST /api/drafts/{draft_id}/finalize` marks the draft final and sets
the project status to `approved`.

---

## Router: meta (`/api/meta`)

Drives wizard dropdowns and the scorecard UI. No request body.

| Method | Path        | Purpose                            | Response shape |
|--------|-------------|------------------------------------|----------------|
| GET    | `/api/meta` | Enumerations + feature flags for the UI | object (below) |

Response fields: `content_types` (`[{value,label}]`), `platforms`,
`funnel_stages`, `tones`, `business_goals`, `lengths`, `statuses`,
`editor_actions` (`[{action,label}]`), `score_categories` (`[{key,label,desc}]`),
`ai_enabled`, `research_enabled`, `ai_provider`.

---

## Router: brands (`/api/brands`)

Brand profile CRUD. Request body is `BrandIn`; responses are `BrandOut`.
Ownership enforced: a brand not owned by the current user returns `404`.

| Method | Path                 | Purpose            | Path params | Body     | Response            |
|--------|----------------------|--------------------|-------------|----------|---------------------|
| GET    | `/api/brands`        | List user's brands | —           | —        | `list[BrandOut]`    |
| POST   | `/api/brands`        | Create brand       | —           | `BrandIn`| `BrandOut` (201)    |
| GET    | `/api/brands/{brand_id}` | Get one brand  | `brand_id`  | —        | `BrandOut`          |
| PUT    | `/api/brands/{brand_id}` | Update brand   | `brand_id`  | `BrandIn`| `BrandOut`          |
| DELETE | `/api/brands/{brand_id}` | Delete brand   | `brand_id`  | —        | empty (204)         |

**`BrandIn`**: `name` (required); plus optional `company_name`, `website`,
`industry`, `audience`, `products_services`, `brand_voice`, `words_to_use`
(list[str]), `words_to_avoid` (list[str]), `competitors` (list[str]),
`differentiators`, `proof_points`, `offers`, `compliance_rules`,
`preferred_cta_language`, `style_preferences` (dict), `approved_boilerplate`,
`team_notes`.
**`BrandOut`**: all of `BrandIn` plus `id`, `created_at`, `updated_at`.

---

## Router: projects (`/api/projects`)

Project CRUD plus the research and generate workflow steps. Ownership enforced
(`404` if the project is not the current user's). Request body for CRUD is
`ProjectIn`; CRUD responses are `ProjectOut`.

| Method | Path                                  | Purpose                  | Path params  | Query | Body        | Response                |
|--------|---------------------------------------|--------------------------|--------------|-------|-------------|-------------------------|
| GET    | `/api/projects`                       | List user's projects     | —            | —     | —           | `list[ProjectOut]`      |
| POST   | `/api/projects`                       | Create project           | —            | —     | `ProjectIn` | `ProjectOut` (201)      |
| GET    | `/api/projects/{project_id}`          | Get one project          | `project_id` | —     | —           | `ProjectOut`            |
| PUT    | `/api/projects/{project_id}`          | Update project           | `project_id` | —     | `ProjectIn` | `ProjectOut`            |
| DELETE | `/api/projects/{project_id}`          | Delete project           | `project_id` | —     | —           | empty (204)             |
| POST   | `/api/projects/{project_id}/research` | Generate research brief  | `project_id` | —     | —           | `ResearchOut`           |
| GET    | `/api/projects/{project_id}/research` | Latest research brief    | `project_id` | —     | —           | `ResearchOut` or `null` |
| POST   | `/api/projects/{project_id}/generate` | Generate a new draft     | `project_id` | —     | —           | `DraftOut`              |
| GET    | `/api/projects/{project_id}/drafts`   | List drafts (desc version)| `project_id`| —     | —           | `list[DraftOut]`        |

**`ProjectIn`** (all optional with defaults): `brand_id` (int|null), `title`
(default `"Untitled"`), `campaign`, `platform`, `content_type`, `objective`,
`target_audience`, `business_goal`, `funnel_stage`, `tone`, `cta`, `length`
(default `"medium"`), `keywords` (list[str]), `offer`, `industry`, `competitors`
(list[str]), `geo_market`, `compliance`, `desired_outcome`, `status` (default
`"idea"`).
**`ProjectOut`**: all of `ProjectIn` plus `id`, `created_at`, `updated_at`.

**`ResearchOut`**: `id`, `project_id`, `trends`, `high_performing_patterns`,
`competitor_observations`, `audience_pain_points`, `content_gaps`,
`common_hooks`, `keywords`, `related_questions` (all lists), `search_intent`,
`recommended_angle`, `recommended_hook`, `recommended_cta`, `risks`,
`market_context`, `model_used`, `generated_at`.

**`DraftOut`**: `id`, `project_id`, `version`, `title`, `body`, `structured`
(dict), `headline_options`, `cta_options`, `hook_options` (lists), `rationale`,
`posting_guidance`, `repurposing_suggestions`, `recommended_edits` (lists),
`is_final`, `model_used`, `created_at`.

Side effects: `POST .../research` flips project status `idea` -> `researching`
and persists `research_sources`. `POST .../generate` auto-increments draft
`version` and flips status `idea`/`researching` -> `drafted`.

---

## Router: drafts (`/api/drafts`)

Draft-level operations: read/edit, score, revise, repurpose, finalize, tag,
export. Ownership enforced through the draft's parent project (`404` otherwise).

| Method | Path                                  | Purpose                         | Path params        | Body          | Response               |
|--------|---------------------------------------|---------------------------------|--------------------|---------------|------------------------|
| GET    | `/api/drafts/{draft_id}`              | Get a draft                     | `draft_id`         | —             | `DraftOut`             |
| PUT    | `/api/drafts/{draft_id}/body`         | Persist manual title/body edits | `draft_id`         | raw dict      | `DraftOut`             |
| POST   | `/api/drafts/{draft_id}/score`        | Score the draft                 | `draft_id`         | —             | `ScoreOut`             |
| GET    | `/api/drafts/{draft_id}/score`        | Latest score                    | `draft_id`         | —             | `ScoreOut` or `null`   |
| POST   | `/api/drafts/{draft_id}/revise`       | Apply an editor action          | `draft_id`         | `ReviseIn`    | `DraftOut`             |
| GET    | `/api/drafts/{draft_id}/revisions`    | Revision history (desc)         | `draft_id`         | —             | `list` (below)         |
| POST   | `/api/drafts/{draft_id}/repurpose`    | Repurpose to other platforms    | `draft_id`         | `RepurposeIn` | `{outputs: ...}`       |
| POST   | `/api/drafts/{draft_id}/finalize`     | Mark final; project -> approved | `draft_id`         | —             | `DraftOut`             |
| POST   | `/api/drafts/{draft_id}/tags`         | Add/attach a tag                | `draft_id`         | `TagIn`       | `DraftOut`             |
| GET    | `/api/drafts/{draft_id}/export/{fmt}` | Export/download draft           | `draft_id`, `fmt`  | —             | file stream/attachment |

**`PUT .../body`** body: a raw JSON object; honored keys are `body` and/or
`title`.

**`ReviseIn`**: `action` (required), `instruction` (default `""`), `body`
(optional — if omitted the draft's current body is used). Persists a
`revision_history` row (before/after) and overwrites `draft.body`.

**`GET .../revisions`** response: list of
`{id, action, instruction, before_text, after_text, created_at}`.

**`RepurposeIn`**: `targets` (list[str]|null), `body` (optional — defaults to the
draft body). Response: `{ "outputs": <repurpose engine result> }`.

**`TagIn`**: `name` (required), `color` (default `"#6366f1"`). Reuses an existing
tag with the same name for the user, else creates it.

**`ScoreOut`**: `id`, `draft_id`, `overall` (int), `categories` (dict),
`summary`, `created_at`.

**`{fmt}` export formats**: `docx`, plus `markdown` (.md), `html` (.html),
`text` (.txt), `csv` (.csv). Unsupported formats return `400`. Each export
writes an `export_history` row and returns the file as an attachment with a
sanitized filename derived from the draft title.

---

## Router: library (`/api/library`)

Read-only search/browse across all of the user's drafts joined to their
projects.

| Method | Path           | Purpose                | Query params                                  | Response               |
|--------|----------------|------------------------|-----------------------------------------------|------------------------|
| GET    | `/api/library` | Search/filter drafts   | `q`, `platform`, `content_type`, `status` (all optional) | `{count, items}` |

Filtering: `platform`, `content_type`, `status` match the parent project; `q` is
a case-insensitive substring across draft title/body and project title/campaign.
Each item: `{draft_id, project_id, title, brand_id, platform, content_type,
campaign, status, version, is_final, score (latest overall or null),
target_audience, cta, tags (list of names), created_at}`.

---

## Router: calendar (`/api/calendar`)

Content calendar CRUD, user-scoped (`404` for entries not owned by the user).
Request body is `CalendarIn`.

| Method | Path                       | Purpose          | Path params | Body         | Response          |
|--------|----------------------------|------------------|-------------|--------------|-------------------|
| GET    | `/api/calendar`            | List entries (by date) | —     | —            | `list` of entries |
| POST   | `/api/calendar`            | Create entry     | —           | `CalendarIn` | `{id}` (201)      |
| PUT    | `/api/calendar/{entry_id}` | Update entry     | `entry_id`  | `CalendarIn` | `{id}`            |
| DELETE | `/api/calendar/{entry_id}` | Delete entry     | `entry_id`  | —            | empty (204)       |

**`CalendarIn`**: `title` (required), `platform` (default `""`),
`scheduled_date` (datetime, required), `status` (default `"scheduled"`), `notes`
(default `""`), `project_id` (int|null), `draft_id` (int|null).
List item shape: `{id, title, platform, scheduled_date, status, notes,
project_id, draft_id}`.

---

## Router: settings (`/api/settings`)

Admin/Settings: platform rules, style-guide rules, the AP-style checker, saved
snippets, and per-user app settings.

### Platform rules

| Method | Path                                   | Purpose             | Path params | Body      | Response   |
|--------|----------------------------------------|---------------------|-------------|-----------|------------|
| GET    | `/api/settings/platform-rules`         | List all platform rules | —       | —         | `list`     |
| PUT    | `/api/settings/platform-rules/{rule_id}` | Update a rule     | `rule_id`   | raw dict  | `{id}`     |

`PUT` honored keys: `label`, `structure`, `best_practices`, `constraints`.
List item: `{id, platform, content_type, label, structure, best_practices,
constraints, is_system}`.

### Style-guide rules

| Method | Path                                       | Purpose                         | Path params | Body          | Response          |
|--------|--------------------------------------------|---------------------------------|-------------|---------------|-------------------|
| GET    | `/api/settings/style-rules`                | List system + user rules        | —           | —             | `list`            |
| POST   | `/api/settings/style-rules`                | Create user rule                | —           | `StyleRuleIn` | `{id}` (201)      |
| PUT    | `/api/settings/style-rules/{rule_id}`      | Edit user rule (system rules rejected, 400) | `rule_id` | `StyleRuleIn` | `{id}` |
| POST   | `/api/settings/style-rules/{rule_id}/toggle` | Toggle enabled flag           | `rule_id`   | —             | `{id, enabled}`   |
| DELETE | `/api/settings/style-rules/{rule_id}`      | Delete user rule (not system)   | `rule_id`   | —             | empty (204)       |

**`StyleRuleIn`**: `name` (required), `category` (default `"clarity"`), `rule`
(required), `detection` (dict), `severity` (default `"warning"`), `brand_id`
(int|null), `enabled` (default `True`).
List item: `{id, name, category, rule, detection, severity, is_system, enabled,
brand_id}`.

### AP-style checker

| Method | Path                      | Purpose                      | Body     | Response               |
|--------|---------------------------|------------------------------|----------|------------------------|
| POST   | `/api/settings/ap-check`  | Run AP/style check on text   | raw dict | AP-style check result  |

Body: raw JSON with a `text` key. Applies enabled system + user style rules.

### Saved snippets

| Method | Path                                  | Purpose                | Path params  | Query  | Body        | Response     |
|--------|---------------------------------------|------------------------|--------------|--------|-------------|--------------|
| GET    | `/api/settings/snippets`              | List snippets          | —            | `kind` | —           | `list`       |
| POST   | `/api/settings/snippets`              | Create snippet         | —            | —      | `SnippetIn` | `{id}` (201) |
| DELETE | `/api/settings/snippets/{snippet_id}` | Delete snippet         | `snippet_id` | —      | —           | empty (204)  |

**`SnippetIn`**: `kind` (required, e.g. `cta`/`offer`/`audience`/`compliance`),
`label` (required), `value` (default `""`).
List item: `{id, kind, label, value}`.

### App settings (key/value)

| Method | Path                  | Purpose                  | Body        | Response          |
|--------|-----------------------|--------------------------|-------------|-------------------|
| GET    | `/api/settings/app`   | Get all user settings    | —           | `{key: value}`    |
| PUT    | `/api/settings/app`   | Upsert one setting       | `SettingIn` | `{key, value}`    |

**`SettingIn`**: `key` (required), `value` (required).
