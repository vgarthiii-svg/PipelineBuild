# Database Schema — Content Creator Engine

This document describes the persistent data model defined in
`backend/app/models.py`. All tables are SQLAlchemy ORM models bound to the
shared `Base` declared in `backend/app/database.py`.

## Portability (SQLite / PostgreSQL)

The schema is written to run unchanged on both SQLite and PostgreSQL:

- List- and dict-shaped fields use the **portable SQLAlchemy `JSON` type**, which
  maps to a native JSON/JSONB on PostgreSQL and to a serialized TEXT column on
  SQLite. JSON columns are flagged in each table below.
- `DateTime` columns store UTC timestamps. The helper `_now()` returns
  `datetime.now(timezone.utc)`. Columns with `default=_now` are stamped on
  insert; columns that also declare `onupdate=_now` are re-stamped on update.
- Foreign keys declare explicit `ondelete` behavior (`CASCADE` or `SET NULL`).
  On SQLite, cascading deletes additionally rely on SQLAlchemy ORM
  `cascade="all, delete-orphan"` relationships (also defined here), so they work
  regardless of whether SQLite foreign-key enforcement is enabled.

---

## Entity-Relationship Overview

```
                                  +-----------+
                                  |   users   |
                                  +-----------+
                                       | 1
        +------------------------------+-----------------------------+
        | 1                            | 1                           | 1
        v *                            v *                           v *
+----------------+            +------------------+          +-------------------+
| brand_profiles |            | content_projects |          | content_calendar  |
+----------------+            +------------------+          +-------------------+
        ^ 0..1                  | 1          | 1            (project_id, draft_id
        | (brand_id, SET NULL)  |            |               are nullable refs)
        +-----------------------+            |
                                |            |
                  1             |            |  1
          +-------------------+ |            | +---------------------+
          v *                   v            v                       v *
   +----------------+   +---------------+   +----------------+
   | research_briefs|   |content_drafts |   |  (drafts ...)  |
   +----------------+   +---------------+
          | 1                 | 1  | 1  | 1
          v *                 v *  v *  v *  \  (M:N via content_tags)
  +-----------------+   +--------+ +-----------------+   +------+
  |research_sources |   | scores | |revision_history |   | tags |
  +-----------------+   +--------+ +-----------------+   +------+
                                |
                                | 1
                                v *
                        +----------------+
                        | export_history |
                        +----------------+

users ---1:*--- style_guide_rules  (user_id nullable; system rules have user_id NULL)
users ---1:*--- saved_snippets
users ---1:*--- app_settings
brand_profiles ---0..1:*--- style_guide_rules (brand_id nullable)

platform_rules  : global/system table, not owned by a user
```

Legend: `1` and `*` denote the cardinality ends of each relationship; `0..1`
denotes an optional (nullable) foreign key.

---

## users

User accounts. In single-user mode a default user is auto-provisioned (see auth
notes in API docs). Owns brands and projects.

| Column      | Type         | Notes                                  |
|-------------|--------------|----------------------------------------|
| id          | Integer      | Primary key                            |
| email       | String(255)  | Unique, indexed                        |
| name        | String(255)  | Default `""`                           |
| created_at  | DateTime     | Default `_now` (UTC)                   |

Relationships:
- `brands` -> `brand_profiles` (1:*, cascade delete-orphan)
- `projects` -> `content_projects` (1:*, cascade delete-orphan)

---

## brand_profiles

Reusable brand/voice context that feeds research, generation, and scoring.

| Column                 | Type         | Notes                                   |
|------------------------|--------------|-----------------------------------------|
| id                     | Integer      | Primary key                             |
| user_id                | Integer FK   | -> `users.id` ON DELETE CASCADE, indexed|
| name                   | String(255)  | Required                                |
| company_name           | String(255)  | Default `""`                            |
| website                | String(512)  | Default `""`                            |
| industry               | String(255)  | Default `""`                            |
| audience               | Text         | Default `""`                            |
| products_services      | Text         | Default `""`                            |
| brand_voice            | Text         | Default `""`                            |
| words_to_use           | JSON (list)  | Default `[]`                            |
| words_to_avoid         | JSON (list)  | Default `[]`                            |
| competitors            | JSON (list)  | Default `[]`                            |
| differentiators        | Text         | Default `""`                            |
| proof_points           | Text         | Default `""`                            |
| offers                 | Text         | Default `""`                            |
| compliance_rules       | Text         | Default `""`                            |
| preferred_cta_language | Text         | Default `""`                            |
| style_preferences      | JSON (dict)  | Default `{}`                            |
| approved_boilerplate   | Text         | Default `""`                            |
| team_notes             | Text         | Default `""`                            |
| created_at             | DateTime     | Default `_now`                          |
| updated_at             | DateTime     | Default `_now`, `onupdate=_now`         |

Relationships:
- `user` -> `users` (many:1)
- `projects` -> `content_projects` (1:*)

---

## content_projects

A single content request/campaign capturing all wizard inputs. Parent of
research briefs and drafts.

| Column          | Type          | Notes                                            |
|-----------------|---------------|--------------------------------------------------|
| id              | Integer       | Primary key                                      |
| user_id         | Integer FK    | -> `users.id` ON DELETE CASCADE, indexed         |
| brand_id        | Integer FK?   | -> `brand_profiles.id` ON DELETE SET NULL, nullable |
| title           | String(512)   | Default `"Untitled"`                             |
| campaign        | String(255)   | Default `""`                                     |
| platform        | String(64)    | Default `""`                                     |
| content_type    | String(64)    | Default `""`                                     |
| objective       | Text          | Default `""`                                     |
| target_audience | Text          | Default `""`                                     |
| business_goal   | String(255)   | Default `""`                                     |
| funnel_stage    | String(64)    | Default `""`                                     |
| tone            | String(128)   | Default `""`                                     |
| cta             | Text          | Default `""`                                     |
| length          | String(64)    | Default `"medium"`                               |
| keywords        | JSON (list)   | Default `[]`                                      |
| offer           | Text          | Default `""`                                     |
| industry        | String(255)   | Default `""`                                     |
| competitors     | JSON (list)   | Default `[]`                                      |
| geo_market      | String(255)   | Default `""`                                     |
| compliance      | Text          | Default `""`                                     |
| desired_outcome | Text          | Default `""`                                     |
| status          | String(32)    | Default `"idea"`, indexed                        |
| created_at      | DateTime      | Default `_now`                                   |
| updated_at      | DateTime      | Default `_now`, `onupdate=_now`                  |

Relationships:
- `user` -> `users` (many:1)
- `brand` -> `brand_profiles` (many:1, optional)
- `briefs` -> `research_briefs` (1:*, cascade delete-orphan)
- `drafts` -> `content_drafts` (1:*, cascade delete-orphan)

---

## research_briefs

AI-generated research output for a project (trends, hooks, recommendations).

| Column                   | Type        | Notes                                  |
|--------------------------|-------------|----------------------------------------|
| id                       | Integer     | Primary key                            |
| project_id               | Integer FK  | -> `content_projects.id` ON DELETE CASCADE, indexed |
| trends                   | JSON (list) | Default `[]`                           |
| high_performing_patterns | JSON (list) | Default `[]`                           |
| competitor_observations  | JSON (list) | Default `[]`                           |
| audience_pain_points     | JSON (list) | Default `[]`                           |
| content_gaps             | JSON (list) | Default `[]`                           |
| common_hooks             | JSON (list) | Default `[]`                           |
| keywords                 | JSON (list) | Default `[]`                           |
| related_questions        | JSON (list) | Default `[]`                           |
| search_intent            | Text        | Default `""`                           |
| recommended_angle        | Text        | Default `""`                           |
| recommended_hook         | Text        | Default `""`                           |
| recommended_cta          | Text        | Default `""`                           |
| risks                    | Text        | Default `""`                           |
| market_context           | Text        | Default `""`                           |
| model_used               | String(128) | Default `""`                           |
| generated_at             | DateTime    | Default `_now`                         |

Relationships:
- `project` -> `content_projects` (many:1)
- `sources` -> `research_sources` (1:*, cascade delete-orphan)

---

## research_sources

Citations/sources attached to a research brief.

| Column       | Type         | Notes                                          |
|--------------|--------------|------------------------------------------------|
| id           | Integer      | Primary key                                    |
| brief_id     | Integer FK   | -> `research_briefs.id` ON DELETE CASCADE, indexed |
| title        | String(512)  | Default `""`                                   |
| url          | String(1024) | Default `""`                                   |
| snippet      | Text         | Default `""`                                   |
| source_type  | String(64)   | Default `"web"`                                |
| retrieved_at | DateTime     | Default `_now`                                 |

Relationships:
- `brief` -> `research_briefs` (many:1)

---

## content_drafts

A generated content draft, versioned per project. Parent of scores, revisions,
exports; tagged via the `content_tags` association table.

| Column                  | Type         | Notes                                          |
|-------------------------|--------------|------------------------------------------------|
| id                      | Integer      | Primary key                                    |
| project_id              | Integer FK   | -> `content_projects.id` ON DELETE CASCADE, indexed |
| version                 | Integer      | Default `1`                                    |
| title                   | String(512)  | Default `""`                                   |
| body                    | Text         | Default `""`                                   |
| structured              | JSON (dict)  | Platform-specific sections; default `{}`       |
| headline_options        | JSON (list)  | Default `[]`                                   |
| cta_options             | JSON (list)  | Default `[]`                                   |
| hook_options            | JSON (list)  | Default `[]`                                   |
| rationale               | Text         | Default `""`                                   |
| posting_guidance        | Text         | Default `""`                                   |
| repurposing_suggestions | JSON (list)  | Default `[]`                                   |
| recommended_edits       | JSON (list)  | Default `[]`                                   |
| is_final                | Boolean      | Default `False`                                |
| model_used              | String(128)  | Default `""`                                   |
| created_at              | DateTime     | Default `_now`                                 |

Relationships:
- `project` -> `content_projects` (many:1)
- `scores` -> `scores` (1:*, cascade delete-orphan)
- `revisions` -> `revision_history` (1:*, cascade delete-orphan)
- `tags` -> `tags` (M:N via `content_tags`)

---

## scores

Scorecard results for a draft. Multiple scores accrue over time; the latest is
read by `GET /api/drafts/{id}/score`.

| Column     | Type        | Notes                                                     |
|------------|-------------|-----------------------------------------------------------|
| id         | Integer     | Primary key                                               |
| draft_id   | Integer FK  | -> `content_drafts.id` ON DELETE CASCADE, indexed         |
| overall    | Integer     | Default `0`                                               |
| categories | JSON (dict) | `{key: {"score": int, "working": str, "weak": str, "improvements": [..]}}` |
| summary    | Text        | Default `""`                                              |
| created_at | DateTime    | Default `_now`                                            |

Relationships:
- `draft` -> `content_drafts` (many:1)

---

## revision_history

Audit log of editor revisions applied to a draft (before/after text per action).

| Column      | Type        | Notes                                                  |
|-------------|-------------|--------------------------------------------------------|
| id          | Integer     | Primary key                                            |
| draft_id    | Integer FK  | -> `content_drafts.id` ON DELETE CASCADE, indexed      |
| action      | String(64)  | e.g. `rewrite`, `shorten`, `expand`, `ap_style`        |
| instruction | Text        | Default `""`                                           |
| before_text | Text        | Default `""`                                           |
| after_text  | Text        | Default `""`                                           |
| created_at  | DateTime    | Default `_now`                                         |

Relationships:
- `draft` -> `content_drafts` (many:1)

---

## platform_rules

System/global rules describing the structure, best practices, and constraints
for each platform + content-type pairing. Not owned by a user.

Unique constraint: `uq_platform_type` on (`platform`, `content_type`).

| Column         | Type        | Notes                                            |
|----------------|-------------|--------------------------------------------------|
| id             | Integer     | Primary key                                      |
| platform       | String(64)  | Indexed                                          |
| content_type   | String(64)  | Indexed                                          |
| label          | String(255) | Default `""`                                     |
| structure      | JSON (list) | Ordered sections; default `[]`                   |
| best_practices | JSON (list) | Default `[]`                                      |
| constraints    | JSON (dict) | Length, hashtags, emoji policy; default `{}`     |
| is_system      | Boolean     | Default `True`                                   |
| updated_at     | DateTime    | Default `_now`, `onupdate=_now`                  |

No ORM relationships (standalone reference table).

---

## style_guide_rules

User-defined and system style/clarity rules used by scoring and the AP-style
checker. System rules have `user_id` NULL and `is_system=True`; user rules carry
the owner's `user_id`. May optionally be scoped to a brand via `brand_id`.

| Column    | Type        | Notes                                                       |
|-----------|-------------|-------------------------------------------------------------|
| id        | Integer     | Primary key                                                 |
| user_id   | Integer FK? | -> `users.id` ON DELETE CASCADE, nullable, indexed          |
| brand_id  | Integer FK? | -> `brand_profiles.id` ON DELETE CASCADE, nullable          |
| name      | String(255) | Required                                                    |
| category  | String(64)  | Default `"clarity"`                                         |
| rule      | Text        | Required                                                    |
| detection | JSON (dict) | `{"type": "regex"|"phrase"|"heuristic", "pattern": str, "message": str}` |
| severity  | String(16)  | Default `"warning"` (`info` / `warning` / `error`)          |
| is_system | Boolean     | Default `False`                                            |
| enabled   | Boolean     | Default `True`                                             |

No ORM relationships defined (referenced via FKs only).

---

## content_calendar

Scheduled content entries owned by a user, optionally linked to a project and/or
a draft.

| Column         | Type        | Notes                                                  |
|----------------|-------------|--------------------------------------------------------|
| id             | Integer     | Primary key                                            |
| user_id        | Integer FK  | -> `users.id` ON DELETE CASCADE, indexed               |
| project_id     | Integer FK? | -> `content_projects.id` ON DELETE SET NULL, nullable  |
| draft_id       | Integer FK? | -> `content_drafts.id` ON DELETE SET NULL, nullable    |
| title          | String(512) | Required                                               |
| platform       | String(64)  | Default `""`                                           |
| scheduled_date | DateTime    | Indexed                                                |
| status         | String(32)  | Default `"scheduled"`                                  |
| notes          | Text        | Default `""`                                           |
| created_at     | DateTime    | Default `_now`                                         |

No ORM relationships defined (referenced via FKs only).

---

## export_history

Record of each export of a draft (format + generated filename).

| Column     | Type        | Notes                                              |
|------------|-------------|----------------------------------------------------|
| id         | Integer     | Primary key                                        |
| draft_id   | Integer FK  | -> `content_drafts.id` ON DELETE CASCADE, indexed  |
| fmt        | String(16)  | Export format (e.g. `docx`, `markdown`, `html`, `text`, `csv`) |
| filename   | String(512) | Default `""`                                       |
| created_at | DateTime    | Default `_now`                                     |

No ORM relationships defined (referenced via FK only).

---

## tags

User-scoped tags applied to drafts.

Unique constraint: `uq_user_tag` on (`user_id`, `name`).

| Column   | Type       | Notes                                          |
|----------|------------|------------------------------------------------|
| id       | Integer    | Primary key                                    |
| user_id  | Integer FK | -> `users.id` ON DELETE CASCADE, indexed       |
| name     | String(64) | Required                                       |
| color    | String(16) | Default `"#6366f1"`                            |

Relationships:
- `drafts` -> `content_drafts` (M:N via `content_tags`)

---

## content_tags (association table)

Many-to-many join between `content_drafts` and `tags`. Composite primary key.

| Column   | Type       | Notes                                          |
|----------|------------|------------------------------------------------|
| draft_id | Integer FK | -> `content_drafts.id` ON DELETE CASCADE, PK   |
| tag_id   | Integer FK | -> `tags.id` ON DELETE CASCADE, PK             |

---

## saved_snippets

Reusable CTAs, offers, audiences, and compliance notes for Settings/Admin.

| Column     | Type        | Notes                                          |
|------------|-------------|------------------------------------------------|
| id         | Integer     | Primary key                                    |
| user_id    | Integer FK  | -> `users.id` ON DELETE CASCADE, indexed       |
| kind       | String(32)  | Indexed (`cta` / `offer` / `audience` / `compliance`) |
| label      | String(255) | Required                                       |
| value      | Text        | Default `""`                                   |
| created_at | DateTime    | Default `_now`                                 |

No ORM relationships defined (referenced via FK only).

---

## app_settings

Per-user key/value settings (e.g. default export format, provider preferences).

Unique constraint: `uq_user_setting` on (`user_id`, `key`).

| Column  | Type       | Notes                                          |
|---------|------------|------------------------------------------------|
| id      | Integer    | Primary key                                    |
| user_id | Integer FK | -> `users.id` ON DELETE CASCADE, indexed       |
| key     | String(64) | Required                                       |
| value   | Text       | Default `""`                                   |

No ORM relationships defined (referenced via FK only).
