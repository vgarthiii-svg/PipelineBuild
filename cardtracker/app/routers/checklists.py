import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChecklistSet, ChecklistItem
from app.schemas import (
    ChecklistSetCreate, ChecklistSetOut, ChecklistItemIn, ChecklistItemOut,
)

router = APIRouter(prefix="/api/checklists", tags=["checklists"])


def _set_summary(db: Session, s: ChecklistSet) -> dict:
    total = db.query(func.count(ChecklistItem.id)).filter(ChecklistItem.set_id == s.id).scalar() or 0
    owned = (
        db.query(func.count(ChecklistItem.id))
        .filter(ChecklistItem.set_id == s.id, ChecklistItem.owned.is_(True))
        .scalar()
        or 0
    )
    pct = round(owned / total * 100.0, 1) if total else 0.0
    return {
        "id": s.id, "name": s.name, "year": s.year, "brand": s.brand,
        "sport": s.sport, "notes": s.notes,
        "total_items": total, "owned_items": owned, "pct_complete": pct,
    }


@router.post("", response_model=ChecklistSetOut)
def create_set(payload: ChecklistSetCreate, db: Session = Depends(get_db)):
    s = ChecklistSet(**payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return _set_summary(db, s)


@router.get("", response_model=list[ChecklistSetOut])
def list_sets(db: Session = Depends(get_db)):
    sets = db.query(ChecklistSet).order_by(ChecklistSet.id.desc()).all()
    return [_set_summary(db, s) for s in sets]


@router.get("/{set_id}")
def get_set(set_id: int, db: Session = Depends(get_db)):
    s = db.get(ChecklistSet, set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Checklist not found")
    items = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.set_id == set_id)
        .order_by(ChecklistItem.id)
        .all()
    )
    return {
        "set": _set_summary(db, s),
        "items": [ChecklistItemOut.model_validate(i).model_dump() for i in items],
    }


@router.delete("/{set_id}")
def delete_set(set_id: int, db: Session = Depends(get_db)):
    s = db.get(ChecklistSet, set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Checklist not found")
    db.query(ChecklistItem).filter(ChecklistItem.set_id == set_id).delete()
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.post("/{set_id}/items", response_model=ChecklistItemOut)
def add_item(set_id: int, payload: ChecklistItemIn, db: Session = Depends(get_db)):
    if not db.get(ChecklistSet, set_id):
        raise HTTPException(status_code=404, detail="Checklist not found")
    item = ChecklistItem(set_id=set_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{set_id}/import")
def import_items(set_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Import checklist entries from a CSV. Recognized (case-insensitive) headers:
    card_number / number / #, player / name, variation / parallel, owned.
    A header row with none of those still works: col1 = card #, col2 = player.
    """
    if not db.get(ChecklistSet, set_id):
        raise HTTPException(status_code=404, detail="Checklist not found")

    raw = file.file.read().decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(raw))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        return {"imported": 0}

    def norm(h):
        return h.strip().lower()

    header = [norm(h) for h in rows[0]]
    num_aliases = {"card_number", "number", "card #", "card#", "#", "no", "no."}
    name_aliases = {"player", "name", "player name"}
    var_aliases = {"variation", "parallel", "insert", "version"}
    owned_aliases = {"owned", "have", "got"}

    has_header = any(h in num_aliases | name_aliases | var_aliases | owned_aliases for h in header)
    if has_header:
        idx = {
            "num": next((i for i, h in enumerate(header) if h in num_aliases), None),
            "name": next((i for i, h in enumerate(header) if h in name_aliases), None),
            "var": next((i for i, h in enumerate(header) if h in var_aliases), None),
            "owned": next((i for i, h in enumerate(header) if h in owned_aliases), None),
        }
        data_rows = rows[1:]
    else:
        idx = {"num": 0, "name": 1, "var": 2, "owned": None}
        data_rows = rows

    def cell(row, i):
        return row[i].strip() if i is not None and i < len(row) else ""

    truthy = {"1", "true", "yes", "y", "x", "owned", "have"}
    count = 0
    for row in data_rows:
        item = ChecklistItem(
            set_id=set_id,
            card_number=cell(row, idx["num"]),
            player=cell(row, idx["name"]),
            variation=cell(row, idx["var"]),
            owned=cell(row, idx["owned"]).lower() in truthy if idx["owned"] is not None else False,
        )
        db.add(item)
        count += 1
    db.commit()
    return {"imported": count}


@router.put("/items/{item_id}", response_model=ChecklistItemOut)
def update_item(item_id: int, payload: ChecklistItemIn, db: Session = Depends(get_db)):
    item = db.get(ChecklistItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ChecklistItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"ok": True}
