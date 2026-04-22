from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.database import get_db
from app.models import ActivityLog, PipelineEntry, Prospect, Client
from app.schemas import ActivityOut

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("/", response_model=List[ActivityOut])
def get_activity(
    client_id: Optional[int] = None,
    prospect_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(ActivityLog).order_by(ActivityLog.created_at.desc())

    if client_id:
        entry_ids = [
            e.id for e in
            db.query(PipelineEntry.id).filter(PipelineEntry.client_id == client_id).all()
        ]
        q = q.filter(ActivityLog.pipeline_entry_id.in_(entry_ids))

    if prospect_id:
        entry_ids = [
            e.id for e in
            db.query(PipelineEntry.id).filter(PipelineEntry.prospect_id == prospect_id).all()
        ]
        q = q.filter(ActivityLog.pipeline_entry_id.in_(entry_ids))

    if action:
        q = q.filter(ActivityLog.action == action)

    logs = q.offset(offset).limit(limit).all()

    results = []
    for log in logs:
        prospect_name = None
        client_name = None
        if log.pipeline_entry_id:
            entry = db.query(PipelineEntry).filter(PipelineEntry.id == log.pipeline_entry_id).first()
            if entry:
                prospect = db.query(Prospect).filter(Prospect.id == entry.prospect_id).first()
                client = db.query(Client).filter(Client.id == entry.client_id).first()
                prospect_name = prospect.name if prospect else None
                client_name = client.name if client else None

        results.append({
            "id": log.id,
            "pipeline_entry_id": log.pipeline_entry_id,
            "action": log.action,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "notes": log.notes,
            "created_at": log.created_at,
            "prospect_name": prospect_name,
            "client_name": client_name,
        })

    return results


@router.get("/{entry_id}", response_model=List[ActivityOut])
def get_entry_activity(entry_id: int, db: Session = Depends(get_db)):
    logs = (
        db.query(ActivityLog)
        .filter(ActivityLog.pipeline_entry_id == entry_id)
        .order_by(ActivityLog.created_at.desc())
        .all()
    )

    entry = db.query(PipelineEntry).filter(PipelineEntry.id == entry_id).first()
    prospect_name = None
    client_name = None
    if entry:
        prospect = db.query(Prospect).filter(Prospect.id == entry.prospect_id).first()
        client = db.query(Client).filter(Client.id == entry.client_id).first()
        prospect_name = prospect.name if prospect else None
        client_name = client.name if client else None

    return [
        {
            "id": log.id,
            "pipeline_entry_id": log.pipeline_entry_id,
            "action": log.action,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "notes": log.notes,
            "created_at": log.created_at,
            "prospect_name": prospect_name,
            "client_name": client_name,
        }
        for log in logs
    ]
