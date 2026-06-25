"""Content calendar CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ContentCalendarEntry, User
from ..schemas import CalendarIn

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("")
def list_entries(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(
        select(ContentCalendarEntry).where(ContentCalendarEntry.user_id == user.id)
        .order_by(ContentCalendarEntry.scheduled_date)
    ).all()
    return [{"id": r.id, "title": r.title, "platform": r.platform,
             "scheduled_date": r.scheduled_date, "status": r.status, "notes": r.notes,
             "project_id": r.project_id, "draft_id": r.draft_id} for r in rows]


@router.post("", status_code=201)
def create_entry(payload: CalendarIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    entry = ContentCalendarEntry(user_id=user.id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id}


@router.put("/{entry_id}")
def update_entry(entry_id: int, payload: CalendarIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    entry = db.get(ContentCalendarEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(404, "Entry not found")
    for k, v in payload.model_dump().items():
        setattr(entry, k, v)
    db.commit()
    return {"id": entry.id}


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    entry = db.get(ContentCalendarEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(404, "Entry not found")
    db.delete(entry)
    db.commit()
