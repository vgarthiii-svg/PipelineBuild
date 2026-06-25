# Wireframes — Content Creator Engine

Screen-by-screen UI plan for the vanilla-JS SPA. Every view documented here is
implemented in `frontend/js/app.js` and is reachable through the hash router
(`#/<route>`). The shell (`frontend/index.html`) provides a fixed left sidebar +
a top bar + a single `#view` content area that each route renders into.

---

## Global shell & navigation

The app is a single page (`index.html`) with three persistent regions: a left
**sidebar**, a **top bar** with a breadcrumb, and the swappable **view** pane.

```
┌──────────────┬──────────────────────────────────────────────────────────┐
│  ✦ Content   │  <breadcrumb: crumb()>                    [ + New Content ]│  ← .topbar
│    Engine    ├──────────────────────────────────────────────────────────┤
│  Marketing   │                                                            │
│  command     │                                                            │
│  center      │                                                            │
│              │                                                            │
│ 📊 Dashboard │                  #view  (route content)                    │
│ ✨ New       │                                                            │
│ 📚 Library   │                                                            │
│ 🏷️ Brand     │                                                            │
│ 🗓️ Calendar  │                                                            │
│ 📐 Style     │                                                            │
│ ⚙️ Settings  │                                                            │
│              │                                                            │
│ [AI: live ]  │   (pill flips to "AI: mock" when no ANTHROPIC_API_KEY)     │  ← .sidebar-foot
└──────────────┴──────────────────────────────────────────────────────────┘
   .sidebar                                .main
```

**Sidebar nav items** (`#nav .nav-item`, `data-route`):
`dashboard`, `new`, `library`, `brands`, `calendar`, `styleguide`, `settings`.
The active item is highlighted by `render()` toggling `.active` on the matching
`data-route`.

**Top bar** (`.topbar`): a breadcrumb (`#crumb`, set per route via `crumb()`)
and a persistent `+ New Content` button (`onclick="route('new')"`).

**Global overlays:**
- **Toast** (`#toast`) — transient status messages (`toast(msg, err)`), auto-hides after ~3.2s.
- **Modal** (`#modal` / `#modal-body`) — used by Repurpose and Export dialogs;
  click-outside closes it.

**Boot sequence** (`boot()` in app.js): calls `API.meta()`, sets the AI pill
(live vs mock), then routes to `#/dashboard` by default. If the API is
unreachable, the view shows a "Cannot reach API" error.

---

## 1. Dashboard (`#/dashboard`)

Loads projects, brands, and library in parallel. Computes pipeline counts by
status and an average score across scored library items.

```
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ Projects     │ Brand        │ Library      │ Avg Score    │   ← grid-4 stat cards
│   12         │ Profiles  3  │ Items    27  │    78        │
│ All content  │ Reusable     │ Saved drafts │ Across       │
│ projects     │ brand voices │              │ scored drafts│
└──────────────┴──────────────┴──────────────┴──────────────┘

┌───────────────────────────────┬───────────────────────────────┐
│ Pipeline by status            │ Recent projects        [+ New]│
│  [idea]               2        │  Feature launch          [✓]  │  ← row-link → project
│  [researching]        1        │  LinkedIn · linkedin   [drafted]
│  [drafted]            4        │  Q3 webinar                    │
│  [needs review]       1        │  LinkedIn · email   [needs review]
│  [approved]           2        │  …(up to 6)                    │
│  [scheduled]          1        │                                │
│  [published]          1        │  (empty → "No projects yet")   │
│  [archived]           0        │                                │
└───────────────────────────────┴───────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ Workflow   Brand → Research → Draft → Score → Revise → …       │
│ [1. Brand profile][2. Platform][3. Content type][4. Objective] │  ← chips
│ [5. Audience][6. Product][7. Tone][8. CTA][9. Research]        │
│ [10. Strategy brief][11. Draft][12. Score][13. Improve]        │
│ [14. Export][15. Library]                                      │
└──────────────────────────────────────────────────────────────┘
```

**Components:**
- **Stat cards** (`statCard`): Projects (count), Brand Profiles (count),
  Library Items (`lib.count`), Avg Score (mean of items with non-null `score`, or "—").
- **Pipeline-by-status** card: one row per status in `META.statuses` with a
  status `badge` and the count from `byStatus`.
- **Recent projects** card: first 6 projects as `row-link`s (title, `platform · content_type`, status badge); each routes to the project workspace.
- **Workflow** card: 15 ordered, read-only `.chip` labels describing the pipeline.

---

## 2. New Content wizard (`#/new`)

A single scrolling form (`#wiz`) grouped into four labeled steps shown as a
step strip. (The steps are visual section headers over one form — submit creates
the project and routes to the workspace.) Brand options come from `API.brands()`;
dropdown option sets come from `META`.

```
[1. Brand & platform]  2. Content & goal   3. Audience & product   4. Voice & CTA
┌──────────────────────────────────────────────────────────────┐
│ Brand profile [— None / ad-hoc — ▾]   Title [_______________] │  required
│ Platform [▾]      Content type [▾]      Campaign [_________]   │
│ ──────────────────────────────────────────────────────────── │
│ Business goal [▾]            Funnel stage [▾]                  │
│ Objective / what this content must achieve                    │
│ [________________________________________________________]   │  textarea
│ ──────────────────────────────────────────────────────────── │
│ Target audience [____________]   Geographic market [_______]  │
│ Offer / service [____________]   Industry [________________]  │
│ Keywords (comma) [___________]   Competitors (comma) [______] │
│ ──────────────────────────────────────────────────────────── │
│ Tone [▾]   Length [▾ medium]   CTA [____________]             │
│ Compliance considerations [____]  Desired outcome [_________] │
│                                                                │
│ [ Create & open workspace → ]   [ Cancel ]                    │
└──────────────────────────────────────────────────────────────┘
```

**Fields** (exact `name` attributes):
- Brand & platform: `brand_id` (select; `null` if "ad-hoc"), `title` (required),
  `platform`, `content_type`, `campaign`.
- Content & goal: `business_goal`, `funnel_stage`, `objective` (textarea).
- Audience & product: `target_audience`, `geo_market`, `offer`, `industry`,
  `keywords` (comma → list), `competitors` (comma → list).
- Voice & CTA: `tone`, `length` (defaults to "medium"), `cta`, `compliance`,
  `desired_outcome`.

**Behavior:** on submit, `keywords`/`competitors` are split to arrays, `brand_id`
coerced to number-or-null, `API.createProject` is called inside `busy()` (spinner
+ disabled button), then `route('project', id)`.

---

## 3. Project workspace (`#/project/<id>`)

The core working surface. Loads the project, its research brief, and its drafts
(uses `drafts[0]`). Header shows title + status + meta and the two primary
actions; the body is a two-region layout: **research brief** then **draft +
scorecard**.

```
┌──────────────────────────────────────────────────────────────┐
│ Feature launch [drafted]            [🔎 Run research][✨ Generate draft]│
│ LinkedIn · linkedin · Lead generation · MOFU                  │
└──────────────────────────────────────────────────────────────┘
```

(Buttons relabel to "Re-run research" / "Regenerate draft" when those artifacts
already exist.)

### 3a. Research brief panel (`renderBrief`)

Hidden until a brief exists. Two-column layout plus a keyword chip row.

```
┌──────────────────────────────────────────────────────────────┐
│ 🔎 Research brief            <model_used> · <generated_at>     │
│ ┌────────────────────────────┬─────────────────────────────┐ │
│ │ Recommended angle  …       │ Trends (•••)                │ │
│ │ Recommended hook   …       │ High-performing patterns(•••)│ │
│ │ Search intent      …       │ Audience pain points (•••)  │ │
│ │ Risks / compliance …       │ Content gaps (•••)          │ │
│ └────────────────────────────┴─────────────────────────────┘ │
│ ─────────────────────────────────────────────────────────── │
│ [🔑 revops][🔑 analytics][🔑 reporting] …  (keyword chips)    │
└──────────────────────────────────────────────────────────────┘
```

### 3b. Draft editor + scorecard (`renderEditor`)

Two-column `.editor-layout`: editor on the left, an analysis stack on the right.

```
┌───────────────────────────────────┬──────────────────────────┐
│ 📝 Draft editor  v2 · <model>      │ 📊 Scorecard [Score draft]│
│            [💾 Save] [✅ Finalize] │  ┌────┐  Strong           │
│ Toolbar (editor_actions):          │  │ 78 │  <summary…>       │
│ [Rewrite][Shorten][Expand]         │  └────┘  (score ring)     │
│ [More professional][More convers.] │  ┌─ 14 category bars ──┐  │
│ [More direct][Add statistics]      │  │ Platform fit    82 ▰│  │
│ [Add/strengthen CTA][Remove fluff] │  │ Audience fit    75 ▰│  │
│ [Convert to AP style][Generate     │  │ Hook strength   80 ▰│  │
│  variations] [♻️ Repurpose][⬇️ Export]│ … (14 total)          │
│                                    │  └─────────────────────┘  │
│ [Draft title____________________]  │ ┌ Headline / hook options┐│
│ ┌────────────────────────────────┐ │ │ • option   [copy]      ││
│ │  draft body (textarea)         │ │ │ • option   [copy]      ││
│ │                                │ │ └────────────────────────┘│
│ │                                │ │ ┌ CTA options ───────────┐│
│ │                                │ │ │ • Book a demo [copy]   ││
│ └────────────────────────────────┘ │ └────────────────────────┘│
│                                    │ 💡 Rationale  <text>      │
│                                    │ 📌 Posting guidance <text>│
└───────────────────────────────────┴──────────────────────────┘
```

**Editor toolbar** — one button per `META.editor_actions` entry (action/label):
Rewrite, Shorten, Expand, More professional, More conversational, More direct,
Add statistics, Add/strengthen CTA, Remove fluff, Convert to AP style, Generate
variations. Plus `♻️ Repurpose` and `⬇️ Export`. Each action button posts the
current body to `API.revise(draftId, {action, body})` and replaces the textarea
with the revised body.

**Header actions:** `💾 Save` (`API.saveBody`), `✅ Finalize` (saves then
`API.finalize`, returns to workspace).

**Scorecard panel** (`renderScore`):
- **Score ring** (`ring()`) — overall 0–100, colored by band
  (≥85 good / ≥70 accent / ≥50 warn / else bad) with a verdict word
  (Excellent / Strong / Needs work / Weak) and a one-line `summary`.
- **14 category bars** (`.score-grid`) — one `.score-cat` per scoring category,
  showing the label, numeric score (colored), a filled bar (`width:score%`), and
  the first recommended improvement. Hover title shows the "weak" note.
  Categories (from `scoring.SCORE_CATEGORIES`): Platform fit, Audience fit, Hook
  strength, Clarity, Conversion strength, SEO strength, AP-style alignment, Brand
  voice alignment, Originality, Readability, CTA strength, Research support,
  Compliance risk, Engagement potential.
  (`Score draft` saves the body first, then `API.score`; an existing score is
  auto-loaded via `API.getScore` on render.)
- **Headline / hook options** and **CTA options** cards (`optionsCard`) — each
  option rendered with a `copy` button (clipboard). Hidden if empty.
- **💡 Rationale** and **📌 Posting guidance** cards — shown only when present.

**Repurpose modal** (`showRepurpose`): posts the current body to
`API.repurpose`; lists each output as `format` + copy button + rendered content.

**Export modal** (`showExport`): a row of download links for
Markdown / HTML / Plain text / CSV / DOCX (each is `API.exportUrl(id, fmt)`), with
a note that PDF is done by printing the HTML export.

**Empty state:** if no draft exists, the draft area shows "No draft yet. Run
research, then generate a draft."

---

## 4. Content Library (`#/library`)

Search/filter bar over a results table. Platform options are derived from the
distinct platforms present in the loaded items; status options come from
`META.statuses`.

```
┌──────────────────────────────────────────────────────────────┐
│ [Search title, body, campaign…] [All platforms ▾][All status ▾][Search]│
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Title        Platform  Type      Status   Score Ver Created│ │
│ │ Feature… ✅  LinkedIn  linkedin [drafted]  78   v2  6/20/26│ │  ← row-link → project
│ │ Q3 post      LinkedIn  email   [approved]  —    v1  6/19/26│ │
│ └──────────────────────────────────────────────────────────┘ │
│ (empty → "No content yet. Create your first piece.")          │
└──────────────────────────────────────────────────────────────┘
```

**Components:** search input (`q`), platform select, status select, Search button.
Table columns: Title (with ✅ when `is_final`), Platform, Type, Status badge,
Score (colored or "—"), Version (`v<n>`), Created date. Each row routes to its
project. Search calls `API.library(params)` and redraws the table body.

---

## 5. Brand Profiles

### 5a. Grid (`#/brands`)

```
┌──────────────────────────────────────────────────────────────┐
│ Brand profiles                              [ + New brand ]    │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐                  │  ← grid-3 cards
│ │ Northstar  │ │ Acme Co    │ │ …          │                  │
│ │ SaaS       │ │ Fintech    │ │            │                  │
│ │ confident, │ │ bold, …    │ │            │                  │
│ │ plain-spoken                              │                  │
│ │ [clarity][trust]…(words_to_use tags)      │                  │
│ └────────────┘ └────────────┘ └────────────┘                  │
│ (empty → "No brand profiles yet.")                            │
└──────────────────────────────────────────────────────────────┘
```

Each card (`row-link`) shows name, industry, a 90-char voice snippet, and up to
4 `words_to_use` tags; clicking opens the editor.

### 5b. Editor (`#/brand/<id>` or `#/brand/new`)

```
┌──────────────────────────────────────────────────────────────┐
│ Brand / profile name * [______]   Company name [___________]  │
│ Website [______________]          Industry [_______________]  │
│ Audience            [textarea]                                 │
│ Products / services [textarea]                                 │
│ Brand voice         [textarea]                                 │
│ Words to USE (comma) [______]   Words to AVOID (comma) [____]  │
│ Competitors (comma) [_________________________________]       │
│ Differentiators     [textarea]                                 │
│ Proof points        [textarea]                                 │
│ Offers              [textarea]                                 │
│ Preferred CTA language [____]   Compliance rules [_________]   │
│ Approved boilerplate [textarea]                                │
│ Team notes          [textarea]                                 │
│ [ Create brand / Save changes ]  [ Delete ]  [ Cancel ]       │
└──────────────────────────────────────────────────────────────┘
```

**Fields:** `name` (required), `company_name`, `website`, `industry`, `audience`,
`products_services`, `brand_voice`, `words_to_use`/`words_to_avoid`/`competitors`
(comma → arrays), `differentiators`, `proof_points`, `offers`,
`preferred_cta_language`, `compliance_rules`, `approved_boilerplate`,
`team_notes`. Submit calls `createBrand` (new) or `updateBrand` (existing);
Delete (existing only) confirms then `deleteBrand`. Both return to the grid.

---

## 6. Content Calendar (`#/calendar`)

Two-column layout: a scheduling form and the list of scheduled entries.

```
┌───────────────────────────────┬──────────────────────────────┐
│ Add to calendar               │ Scheduled (3)                 │
│ Title [__________________]    │  Launch post              [✕] │
│ Platform [______] Date [📅]   │  LinkedIn · 6/30/26 9:00 AM   │
│ Link project (optional) [▾]   │  Webinar promo            [✕] │
│ Notes [textarea]              │  LinkedIn · 7/02/26 …         │
│ [ Schedule ]                  │  (empty → "Nothing scheduled")│
└───────────────────────────────┴──────────────────────────────┘
```

**Form fields:** `title` (required), `platform`, `scheduled_date`
(`datetime-local`, required, sent as ISO), `project_id` (optional select),
`notes`. The list shows title, `platform · localized date`, and a remove (✕)
button per entry (`API.delCalendar`).

---

## 7. Style Guide (`#/styleguide`)

Two-column layout: an AP-style checker and the editorial rules manager.

```
┌───────────────────────────────┬──────────────────────────────┐
│ 📐 AP-style checker           │ Editorial rules               │
│ [paste content…       ]       │ Rule name [____] Severity [▾] │
│ [paste content…       ]       │ Rule description [__________]  │
│ [ Check ]                     │ Detect type [phrase ▾] Pattern│
│ ┌────┐  Passes / Needs edits  │ [ Add rule ]                  │
│ │ 86 │  132 words · 3 findings │ ───────────────────────────  │
│ └────┘  (ap_score ring)       │ Avoid hype  [warning] system  │
│ • Rule [severity] — message   │   <rule text>      [On][✕]    │
│   (matches…)                  │ Oxford comma [info]           │
│ • …                           │   <rule text>      [Off][✕]   │
└───────────────────────────────┴──────────────────────────────┘
```

**AP checker:** textarea → `API.apCheck(text)`. Result shows an `ap_score` ring,
pass/needs-edits verdict, word count + finding count, and a list of findings
(rule + severity tag + message + first matches).

**Editorial rules form:** `name` (required), `severity` (info/warning/error,
defaults warning), `rule` description (required), `dtype` (phrase list / regex),
`pattern` (comma-separated phrases or a regex). Submits a structured payload with
`detection: {type, pattern, message}` and `category: "custom"`.

**Rules list** (`ruleRow`): each rule shows name + severity tag + a "system"
marker for built-ins, the rule text, an On/Off toggle (`toggleStyleRule`), and a
delete (✕) for non-system rules.

---

## 8. Settings (`#/settings`)

Loads platform rules, snippets, app settings, and health in parallel.

```
┌──────────────────────────────────────────────────────────────┐
│ AI & providers                                                │
│  AI provider  anthropic [live]  (or [mock — set ANTHROPIC_API_KEY])│
│  Research     [live web research] / [synthesized]             │
│  Default export format [markdown ▾]   [ Save ]                │
└──────────────────────────────────────────────────────────────┘
┌───────────────────────────────┬──────────────────────────────┐
│ Saved snippets (CTAs/offers/  │ Platform rules (N)           │
│  audiences)                   │  LinkedIn post   linkedin/…  │
│ [kind ▾][label][value][Add]   │   hook → value → CTA …       │
│  [cta] Book demo  /demo  [✕]  │  Email campaign  email/…     │
│  [offer] Free trial … [✕]     │   subject → body → … (struct)│
│  (empty → "No snippets yet.") │  …(scrollable list)          │
└───────────────────────────────┴──────────────────────────────┘
```

**AI & providers card:** read-only health (`ai_provider`, live/mock; research
live/synthesized) plus a Default export format select (markdown/html/text/csv/docx)
saved via `API.setAppSetting`.

**Saved snippets card:** add form with `kind` (cta/offer/audience/compliance),
`label`, `value`; list shows kind tag + label + value + delete.

**Platform rules card:** read-only list of seeded best-practice rules, each
showing label, `platform/content_type`, and the structure steps joined with `→`.

---

## Component breakdown (shared primitives in `app.js`)

| Component | Function | Used by |
|-----------|----------|---------|
| Stat card | `statCard` | Dashboard |
| Status badge | `badge` | Dashboard, project header, library |
| Score ring | `ring` | Scorecard, AP checker |
| Score color band | `scoreColor` | rings, bars, library scores |
| Options card (+copy) | `optionsCard` | headline/CTA options |
| Scorecard render | `renderScore` | project workspace |
| Research brief render | `renderBrief` | project workspace |
| Draft editor render | `renderEditor` | project workspace |
| Repurpose modal | `showRepurpose` | project workspace |
| Export modal | `showExport` | project workspace |
| Toast | `toast` | global |
| Modal | `modal` / `closeModal` | global |
| Busy/spinner wrapper | `busy` | all async buttons |
| CSV → list | `csvToList` | wizard, brand form |
| Router | `route` / `render` / `ROUTES` | global |
