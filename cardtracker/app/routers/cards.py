import csv
import io
import os
import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db, IMAGE_DIR
from app.models import Card, VALID_STATUSES, STATUS_IN_STOCK
from app.schemas import CardCreate, CardOut, CardUpdate, ExtractResult, UploadResult
from app.vision import extract_card

router = APIRouter(prefix="/api/cards", tags=["cards"])

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _save_upload(upload: UploadFile) -> str:
    """Save an uploaded image under data/images and return its stored filename."""
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if ext not in _ALLOWED_EXT:
        # Fall back to jpeg if the client didn't give a usable extension
        ext = ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(IMAGE_DIR, name)
    with open(dest, "wb") as f:
        f.write(upload.file.read())
    return name


def _max_card_num(db: Session) -> int:
    max_n = 0
    for (cid,) in db.query(Card.card_id).all():
        m = re.match(r"INV-(\d+)", cid or "", re.IGNORECASE)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n


def _next_card_id(db: Session) -> str:
    """Compute the next INV-#### id by scanning existing ids."""
    return f"INV-{_max_card_num(db) + 1:04d}"


# CSV column header -> Card field, for inventory import (matches export.csv)
_IMPORT_MAP = {
    "player": "player", "year": "year", "brand": "brand",
    "set": "set_name", "set name": "set_name", "set_name": "set_name",
    "card #": "card_number", "card number": "card_number", "number": "card_number",
    "card_number": "card_number", "#": "card_number",
    "variation": "variation", "parallel": "variation",
    "team": "team", "sport": "sport", "rookie": "is_rookie", "condition": "condition",
    "status": "status", "purchase date": "purchase_date",
    "purchase source": "purchase_source", "purchased from": "purchase_source",
    "purchase price": "purchase_price", "cost": "purchase_price",
    "sale date": "sale_date", "sale platform": "sale_platform", "sold on": "sale_platform",
    "sale price": "sale_price", "sale fees": "sale_fees", "fees": "sale_fees",
    "sale shipping": "sale_shipping", "shipping": "sale_shipping",
    "est. value": "estimated_value", "estimated value": "estimated_value",
    "notes": "notes", "front image": "front_image", "back image": "back_image",
}
_FLOAT_FIELDS = {"purchase_price", "sale_price", "sale_fees", "sale_shipping", "estimated_value"}


@router.post("/import")
def import_cards(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import inventory from a CSV (the same columns produced by export.csv)."""
    text = file.file.read().decode("utf-8-sig", errors="replace")
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows:
        return {"imported": 0}
    header = [h.strip().lower() for h in rows[0]]
    cols = {i: _IMPORT_MAP[h] for i, h in enumerate(header) if h in _IMPORT_MAP}
    if not cols:
        raise HTTPException(status_code=400, detail="No recognizable columns found (need at least a Player column).")

    n = _max_card_num(db)
    count = 0
    for row in rows[1:]:
        data = {}
        for i, field in cols.items():
            if i >= len(row):
                continue
            val = row[i].strip()
            if not val:
                continue
            if field in _FLOAT_FIELDS:
                try:
                    data[field] = float(val.replace(",", "").replace("$", ""))
                except ValueError:
                    pass
            else:
                data[field] = val
        if not any(data.get(k) for k in ("player", "year", "brand", "set_name", "card_number")):
            continue
        status = (data.pop("status", "") or "").lower().replace(" ", "_")
        if status not in VALID_STATUSES:
            status = STATUS_IN_STOCK
        n += 1
        db.add(Card(card_id=f"INV-{n:04d}", status=status, **data))
        count += 1
    db.commit()
    return {"imported": count}


@router.post("/upload", response_model=UploadResult)
def upload(
    front: UploadFile = File(...),
    back: UploadFile = File(None),
):
    """
    Free path (no AI, no cost): save the front/back photos and return their
    filenames. The browser handles any on-device text scanning itself; this
    endpoint just stores the images.
    """
    front_name = _save_upload(front)
    back_name = _save_upload(back) if back is not None else ""
    return UploadResult(front_image=front_name, back_image=back_name)


@router.post("/extract", response_model=ExtractResult)
def extract(
    front: UploadFile = File(...),
    back: UploadFile = File(None),
):
    """
    Step 1 of adding a card: upload front (and optional back) photos.
    Saves the images and runs Claude Vision to pre-fill the card's fields.
    The images are kept; pass their filenames back to POST /api/cards to save.
    """
    front_name = _save_upload(front)
    back_name = _save_upload(back) if back is not None else ""

    result = extract_card(
        os.path.join(IMAGE_DIR, front_name),
        os.path.join(IMAGE_DIR, back_name) if back_name else None,
    )
    return ExtractResult(
        front_image=front_name,
        back_image=back_name,
        extracted=result["fields"],
        vision_used=result["vision_used"],
        message=result["message"],
    )


@router.post("", response_model=CardOut)
def create_card(payload: CardCreate, db: Session = Depends(get_db)):
    """Step 2: save a reviewed card to inventory. Auto-assigns the next INV id."""
    status = payload.status if payload.status in VALID_STATUSES else "in_stock"
    card = Card(
        card_id=_next_card_id(db),
        status=status,
        front_image=payload.front_image,
        back_image=payload.back_image,
        purchase_price=payload.purchase_price,
        estimated_value=payload.estimated_value,
        purchase_date=payload.purchase_date,
        purchase_source=payload.purchase_source,
        **payload.model_dump(
            include={
                "player", "year", "brand", "set_name", "card_number",
                "variation", "team", "sport", "is_rookie", "condition", "notes",
            }
        ),
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.get("", response_model=list[CardOut])
def list_cards(
    q: str = "",
    status: str = "",
    sport: str = "",
    db: Session = Depends(get_db),
):
    """List inventory with optional text search and status/sport filters."""
    query = db.query(Card)
    if status:
        query = query.filter(Card.status == status)
    if sport:
        query = query.filter(Card.sport == sport)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            func.lower(Card.player).like(like)
            | func.lower(Card.set_name).like(like)
            | func.lower(Card.brand).like(like)
            | func.lower(Card.team).like(like)
            | func.lower(Card.card_id).like(like)
            | func.lower(Card.year).like(like)
        )
    return query.order_by(Card.id.desc()).all()


@router.get("/export.csv")
def export_csv(db: Session = Depends(get_db)):
    """Export the whole inventory as CSV (Google Sheets friendly)."""
    cards = db.query(Card).order_by(Card.card_id).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Card ID", "Player", "Year", "Brand", "Set", "Card #", "Variation",
        "Team", "Sport", "Rookie", "Condition", "Status",
        "Purchase Date", "Purchase Source", "Purchase Price",
        "Sale Date", "Sale Platform", "Sale Price", "Sale Fees", "Sale Shipping",
        "Net Profit", "Est. Value", "Notes", "Front Image", "Back Image",
    ])
    for c in cards:
        writer.writerow([
            c.card_id, c.player, c.year, c.brand, c.set_name, c.card_number,
            c.variation, c.team, c.sport, c.is_rookie, c.condition, c.status,
            c.purchase_date, c.purchase_source,
            c.purchase_price if c.purchase_price is not None else "",
            c.sale_date, c.sale_platform,
            c.sale_price if c.sale_price is not None else "",
            c.sale_fees if c.sale_fees is not None else "",
            c.sale_shipping if c.sale_shipping is not None else "",
            c.net_profit if c.net_profit is not None else "",
            c.estimated_value if c.estimated_value is not None else "",
            c.notes, c.front_image, c.back_image,
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=card_inventory.csv"},
    )


@router.get("/{card_pk}", response_model=CardOut)
def get_card(card_pk: int, db: Session = Depends(get_db)):
    card = db.get(Card, card_pk)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.put("/{card_pk}", response_model=CardOut)
def update_card(card_pk: int, payload: CardUpdate, db: Session = Depends(get_db)):
    card = db.get(Card, card_pk)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in VALID_STATUSES:
        data.pop("status")
    for key, value in data.items():
        setattr(card, key, value)
    db.commit()
    db.refresh(card)
    return card


@router.delete("/{card_pk}")
def delete_card(card_pk: int, db: Session = Depends(get_db)):
    card = db.get(Card, card_pk)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    db.delete(card)
    db.commit()
    return {"ok": True}
