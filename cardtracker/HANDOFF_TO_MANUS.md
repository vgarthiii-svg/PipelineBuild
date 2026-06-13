# Card Tracker — Feature Hand-off Spec (for porting into the Manus mobile app)

This document describes everything the FastAPI/web "Card Tracker" does, so the
same features can be re-built inside the Manus-generated React Native / Expo app
(which already has matching tabs: `add-card`, `inventory`, `card-detail`,
`sales`, `checklists`, `settings`).

The web app is the **reference implementation** — run it and copy the behavior.
None of the code ports directly (different stack); this is a spec, not a copy.

---

## 1. Data model

**Card** (one physical card)
- `card_id` — human id, auto-assigned as `INV-0001`, `INV-0002`, … (next number = max existing + 1)
- Identity: `player, year, brand, set_name, card_number, variation, team, sport, is_rookie, condition, notes`
- `status` — `in_stock` | `listed` | `sold`
- Images: `front_image`, `back_image`
- Purchase: `purchase_price` (cost basis), `purchase_date`, `purchase_source`
- Sale: `sale_price`, `sale_date`, `sale_platform`, `sale_fees`, `sale_shipping`, `sale_notes`
- Derived `net_profit = sale_price − purchase_price − sale_fees − sale_shipping`

**ChecklistSet**: `name, year, brand, sport, notes`
**ChecklistItem**: `set_id, card_number, player, variation, owned (bool)`

---

## 2. Features and behavior

### Inventory + capture
- Capture front (+ optional back) photo → store images → create card with the next `INV-####` id → review/edit fields → save.
- Inventory list: thumbnails, text search (player/set/brand/team/id/year), filter by status.
- Native mapping: `expo-image-picker` / `expo-camera` for capture; the rest is list UI + DB.

### Free on-device card reading (OCR) — replaces paid AI
The web app reads the **back** of the card (scans better than the glossy front) with Tesseract.js, then parses text into fields. Native equivalent: an on-device OCR lib (e.g. ML Kit text recognition / VisionKit) — or Manus's built-in LLM if you accept its usage. Parsing logic to replicate:
- `year`: first `19xx`/`20xx`, or a season like `2023-24`.
- `card_number`: match `#123`, `No. 123`, `Card 123`, `RC-12`.
- `brand`: keyword match — Topps, Panini, Bowman, Upper Deck, Fleer, Donruss, Score, Leaf.
- `set_name`: keyword match — Chrome, Prizm, Select, Mosaic, Optic, Stadium Club, Heritage, Finest, Allen & Ginter, Gallery, Contenders, Chronicles, Sapphire, Gypsy Queen, etc.
- `team` + `sport`: match a team nickname from a per-sport list (Baseball/Basketball/Football/Hockey); the matched team's league sets the sport. Also infer sport from stat words (HR/RBI/ERA → Baseball; REBOUND/ASSIST/PPG → Basketball; YARDS/TOUCHDOWN → Football; GOALS/NHL → Hockey).
- `is_rookie`: text contains "rookie" or "RC".
- `player`: a 2–3 word alphabetic line that is NOT a brand/set/team/keyword; title-case it.
- Always show the result for the user to correct before saving.

### Voice commands — free (browser Web Speech API; native = device speech-to-text)
Mic button → transcribe → parse intent:
- **Add**: starts with add/new/log/create or contains "card" → extract the same fields as OCR (year/brand/set/sport/team/rookie/number; player = leftover words) → prefill the add form.
- **Sold**: contains "sold"/"sell" → target = `INV-####` (parse "inv 5" → `INV-0005`) or a spoken player name; price = number after "for"/"$" → confirm → set status `sold` + `sale_price`.
- **Listed**: contains "list/listed" → target as above → set status `listed`.
- Always confirm the matched card before changing it.
- Native mapping: `expo-speech`/`@react-native-voice/voice` for STT; same parsing logic.

### Purchases & Sales (P&L)
- Record cost basis + purchase date/source on a card.
- Mark sold with price, date, platform, fees, shipping → compute `net_profit` live.
- Sales tab totals: revenue (Σ sale_price of sold), cost_of_sold (Σ purchase_price of sold), fees (Σ fees+shipping), `net_profit = revenue − cost_of_sold − fees`, `roi = net_profit / cost_of_sold × 100`. Plus a per-card profit list.

### Checklists
- Create a set (name optional; defaults to "Untitled checklist").
- **Import-first**: pick a CSV or `.xlsx` file → create the set named from the filename → import rows → open it → fill in name/year/brand/sport after.
- Import column detection (case-insensitive headers, with aliases): `card_number`/`number`/`#`; `player`/`name`; `variation`/`parallel`; `owned`. If no recognizable header row, assume col1 = card number, col2 = player. `owned` truthy = 1/true/yes/y/x.
- Per-set progress: `owned_items / total_items` and `% complete`. Tap items to toggle owned.

### CSV export
- Export the whole inventory as CSV including sale/profit columns.

---

## 3. Reference REST API (web app)

Use these as the shape for the mobile app's data layer (tRPC procedures / DB ops).

```
POST   /api/cards/upload            (multipart front,back) -> {front_image, back_image}   # stores images, no AI
POST   /api/cards                   (json card fields) -> creates card with next INV id
GET    /api/cards?q=&status=&sport= -> list
GET    /api/cards/{id}              -> one
PUT    /api/cards/{id}              -> update (incl. status + sale fields)
DELETE /api/cards/{id}
GET    /api/cards/export.csv        -> CSV
GET    /api/dashboard               -> totals + sales P&L (revenue, cost_of_sold, fees, net_profit, roi)
POST   /api/checklists              -> create set (name optional)
PUT    /api/checklists/{id}         -> edit set details
GET    /api/checklists              -> list with owned/total/pct
GET    /api/checklists/{id}         -> set + items
DELETE /api/checklists/{id}
POST   /api/checklists/{id}/items   -> add item
POST   /api/checklists/{id}/import  (multipart file: .csv or .xlsx) -> {imported: N}
PUT    /api/checklists/items/{id}   -> toggle owned / edit
DELETE /api/checklists/items/{id}
```

---

## 4. Cost note (important)

The web app is **$0 to run**: card reading uses on-device OCR, voice uses the
browser's built-in recognition — no API keys. On the Manus mobile app:
- Camera, voice (device STT), and storage (Manus DB) are free/native.
- Card *reading* can use a native OCR library (free) OR Manus's built-in LLM
  (better accuracy, but counts against Manus usage). Choose per budget.

The full working reference is the repo `vgarthiii-svg/PipelineBuild`, branch
`claude/adoring-mayer-va4m1e`, folder `cardtracker/`.
