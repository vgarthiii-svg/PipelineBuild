# Connecting the App and the Agent

This project has two halves that now work as one pipeline.

| Role | What it is | Where |
|------|-----------|-------|
| **System of record + dashboard** | The web app and its SQLite database | `localhost:8000`, `data/pipeline.db` |
| **The brain (enrichment + scoring + writing)** | Claude, using free web search and connectors | This agent |
| **Import / export interchange** | CSV + markdown files | repo root (`*_prospects.csv`, `*_profile.md`, ...) |

**The database is the source of truth.** Claude enriches and scores, then writes results into the app. Files are how bulk data gets in and reports come out — not a second copy you maintain by hand.

## Load the Decerto pipeline into the app

On your machine, after pulling this branch:

```bash
git pull origin claude/sweet-bardeen-q8zsf1
python -m app.import_decerto        # loads Decerto client + 52 scored accounts
# then open / refresh http://localhost:8000 and pick "Decerto" in the client dropdown
```

The importer is idempotent — run it again anytime to refresh from the CSV.
Result: 52 accounts, scored fit-led (80/20). Shelter shows as **Pass** (chose
Guidewire); the warm Allianz/Generali ties rank **Hot**.

## Load any future sheet (no code)

Any enriched sheet can be loaded into a client's pipeline through the app:

- **API:** `POST /api/pipeline/{client_id}/import-csv` with the CSV file
  (see `http://localhost:8000/docs`). Columns are auto-detected — `Company`,
  `Segment`, `HQ`, `Fit`, `Contact`, `Signal`, `Outreach accelerant`.
- A `Fit` column (1-5) drives the score; a `WARM` accelerant lifts relationship
  strength. Contacts become the account's "Best Contact"; the signal becomes the
  entry's note.

## How scoring maps

- Prospecting lists are scored **fit-led (80/20 PMF/RS)** because most targets
  are cold. Warm group ties still get elevated via relationship strength.
- Tiers: Hot 70+ · Warm 50-69 · Monitor 30-49 · Pass <30.

## What did NOT change

- No database migration. Contacts are stored as `Relationship` rows (already read
  by the dashboard) and signals in the pipeline entry `notes` field.
- `data/pipeline.db` stays out of git; the schema lives in code, the importer
  rebuilds the data.
