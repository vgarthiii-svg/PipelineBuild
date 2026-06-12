# Sports Card Tracker

A mobile-friendly web app to manage a sports card collection/business. Snap the
front and back of a card, let **Claude Vision** read the details, and save it to
a searchable inventory database. Tracks inventory, cost basis, and (in later
phases) purchases, sales P&L, and set checklists.

This lives in a `cardtracker/` subfolder and is completely independent of the
unrelated "BD Pipeline Agent" in the repo root.

## What's built (Phase 1)

- **Scan a card** → front + back photo → Claude Vision extracts player, year,
  brand, set, card #, parallel/insert, team, sport, rookie flag, condition →
  you review/edit → save. Auto-assigns the next `INV-####` id.
- **Inventory** list with thumbnails, text search, and status filters.
- **Dashboard** with totals, in-stock count, cost basis, and profit.
- **Edit / delete** any card; mark as In stock / Listed / Sold.
- **CSV export** (`Card ID, Front Image, Back Image, …`) — feeds your existing
  Google Sheet workflow.
- Works **without an API key** as a fully manual tracker.

## Run it

```bash
bash cardtracker/run.sh
```

Then open <http://localhost:8001>. To scan with your phone's camera, open
`http://<your-computer-ip>:8001` on the phone (same Wi-Fi).

To enable photo auto-fill, put your key in `cardtracker/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## How it fits your current workflow

You currently name files `INV-0001-F.jpg` / `INV-0001-B.jpg` and run a Google
Apps Script to link them into a sheet. This app removes the manual naming and
data entry: the camera capture, id assignment, detail extraction, and storage
all happen in one step. The CSV export keeps you compatible with the sheet if
you still want it.

## Tech

FastAPI + SQLAlchemy (SQLite) + the Anthropic SDK, with a vanilla-JS frontend.
Data (SQLite db + uploaded images) lives in `cardtracker/data/` and is
git-ignored.

## Roadmap

- **Phase 2** — Purchases & Sales ledgers with cost-basis allocation and profit/ROI.
- **Phase 3** — Set checklists with owned/needed tracking and completion %.
