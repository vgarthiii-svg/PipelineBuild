from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Setting, Card, ChecklistSet, ChecklistItem

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULTS = {"app_name": "Card Tracker"}


class SettingsIn(BaseModel):
    app_name: Optional[str] = None


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    values = dict(DEFAULTS)
    for s in db.query(Setting).all():
        values[s.key] = s.value
    return values


@router.put("")
def update_settings(payload: SettingsIn, db: Session = Depends(get_db)):
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        row = db.get(Setting, key)
        if row:
            row.value = value
        else:
            db.add(Setting(key=key, value=value))
    db.commit()
    return get_settings(db)


@router.post("/clear")
def clear_data(scope: str = "cards", db: Session = Depends(get_db)):
    """Delete data. scope='cards' wipes the inventory; scope='all' also wipes checklists."""
    n = db.query(Card).delete()
    if scope == "all":
        db.query(ChecklistItem).delete()
        db.query(ChecklistSet).delete()
    db.commit()
    return {"ok": True, "cleared_cards": n}
