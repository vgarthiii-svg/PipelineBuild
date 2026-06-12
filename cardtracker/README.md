# Sports Card Tracker

A mobile-friendly web app to manage a sports card collection/business. Snap the
front and back of a card, let **Claude Vision** read the details, and save it to
a searchable inventory database. Tracks inventory, cost basis, and (in later
phases) purchases, sales P&L, and set checklists.

This lives in a `cardtracker/` subfolder and is completely independent of the
unrelated "BD Pipeline Agent" in the repo root.

## What's built

**Inventory**
- **Scan a card** → front + back photo → it's stored and logged with the next
  `INV-####` id. A **free on-device text scanner** (runs in your browser, no
  account, no cost) pre-fills what it can read; you review/edit and save.
- Inventory list with thumbnails, text search, and status filters.
- Edit / delete any card; status workflow In stock → Listed → Sold.

**Purchases & Sales (P&L)**
- Record cost basis, purchase date, and source on each card.
- Mark a card sold with sale price, date, platform, fees, and shipping.
- **Sales** tab shows revenue, cost of cards sold, fees, **net profit, and ROI**,
  plus a per-card profit list.

**Set Checklists**
- Create a set (e.g. "2023 Topps Chrome"), add cards or **import a CSV**
  (`card_number, player, owned`), and tick off what you own.
- Progress bars and completion % per set.

**Other**
- **CSV export** of the whole inventory (with sale/profit columns).
- Works **fully free** — no API key required.

### Optional: AI auto-fill (costs money, off by default)
If you ever want higher-accuracy reading of cards, set `ANTHROPIC_API_KEY` in
`.env` and the app can use Claude Vision via the `/api/cards/extract` endpoint.
This is **not** used by the default UI and is not required.

### Where your data lives
Your inventory database and uploaded photos are stored in **`~/CardTrackerData`**
(your home folder), so updating or re-downloading the app never wipes them.
Override with the `CARD_DATA_DIR` environment variable.

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

## Tech

FastAPI + SQLAlchemy (SQLite) backend, vanilla-JS frontend. Free on-device OCR
via Tesseract.js (loaded from a CDN; skipped gracefully when offline).
