import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from pydantic import BaseModel

from app.database import get_db
from app.models import IdentityFilter, Client, PipelineEntry, Prospect
from app.schemas import IdentityFilterCreate, IdentityFilterOut
from app.scoring import run_identity_filter

router = APIRouter(prefix="/api/filters", tags=["filters"])


class FilterPreviewRequest(BaseModel):
    """A candidate filter config to preview (not saved)."""
    allowed_business_models: Optional[List[str]] = None
    allowed_stages: Optional[List[str]] = None
    min_employees: Optional[int] = None
    max_employees: Optional[int] = None
    required_verticals: Optional[List[str]] = None
    excluded_verticals: Optional[List[str]] = None
    required_states: Optional[List[str]] = None


class _PreviewFilterShim:
    """
    Pretends to be an IdentityFilter ORM object so scoring.run_identity_filter
    works unchanged. JSON-list columns store stringified JSON; this mirrors that.
    """
    def __init__(self, cfg: FilterPreviewRequest):
        self.allowed_business_models = json.dumps(cfg.allowed_business_models) if cfg.allowed_business_models else None
        self.allowed_stages = json.dumps(cfg.allowed_stages) if cfg.allowed_stages else None
        self.min_employees = cfg.min_employees
        self.max_employees = cfg.max_employees
        self.required_verticals = json.dumps(cfg.required_verticals) if cfg.required_verticals else None
        self.excluded_verticals = json.dumps(cfg.excluded_verticals) if cfg.excluded_verticals else None
        self.required_states = json.dumps(cfg.required_states) if cfg.required_states else None
        self.notes = None


@router.post("/{client_id}/preview")
def preview_filter_impact(client_id: int, cfg: FilterPreviewRequest, db: Session = Depends(get_db)):
    """
    Simulate a filter against this client's current pipeline WITHOUT saving.
    Returns aggregate counts + per-blocked-company reason list.
    Lets the user see "would block 14 of 53, including Shelter, NatGen, ..." before committing.
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    shim = _PreviewFilterShim(cfg)

    entries = db.query(PipelineEntry).filter(PipelineEntry.client_id == client_id).all()
    total = len(entries)
    blocked = []
    passed = []
    for e in entries:
        prospect = db.query(Prospect).filter(Prospect.id == e.prospect_id).first()
        if not prospect:
            continue
        ok, reason = run_identity_filter(prospect, shim)
        if ok:
            passed.append({"prospect_id": prospect.id, "name": prospect.name})
        else:
            blocked.append({
                "prospect_id": prospect.id,
                "name": prospect.name,
                "reason": reason,
                "type": prospect.type,
                "employees": prospect.employees,
                "tier_currently": e.tier,
                "matchmaker_score": e.matchmaker_score,
            })

    # Group block reasons by category for quick summary
    by_reason = {}
    for b in blocked:
        r = b["reason"]
        by_reason[r] = by_reason.get(r, 0) + 1

    return {
        "total": total,
        "passed": len(passed),
        "blocked": len(blocked),
        "blocked_detail": blocked[:200],  # cap to avoid huge payloads
        "blocked_by_reason": by_reason,
    }


@router.get("/{client_id}/blocked")
def list_currently_blocked(client_id: int, db: Session = Depends(get_db)):
    """
    Return companies currently filtered out by the SAVED filter for this client.
    Uses the `filtered` flag on pipeline_entries (set by scoring run).
    """
    entries = (
        db.query(PipelineEntry)
        .filter(PipelineEntry.client_id == client_id, PipelineEntry.filtered == True)
        .all()
    )
    out = []
    for e in entries:
        prospect = db.query(Prospect).filter(Prospect.id == e.prospect_id).first()
        if not prospect:
            continue
        out.append({
            "entry_id": e.id,
            "prospect_id": prospect.id,
            "name": prospect.name,
            "type": prospect.type,
            "employees": prospect.employees,
            "reason": e.filter_reason,
        })
    return {"count": len(out), "blocked": out}


@router.get("/{client_id}", response_model=IdentityFilterOut)
def get_identity_filter(client_id: int, db: Session = Depends(get_db)):
    f = db.query(IdentityFilter).filter(IdentityFilter.client_id == client_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="No identity filter found for this client")
    return f


@router.post("/{client_id}", response_model=IdentityFilterOut)
def upsert_identity_filter(client_id: int, data: IdentityFilterCreate, db: Session = Depends(get_db)):
    """Create or update identity filter (upsert)."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    f = db.query(IdentityFilter).filter(IdentityFilter.client_id == client_id).first()

    if f:
        for key, val in data.dict(exclude_unset=True).items():
            setattr(f, key, val)
    else:
        f = IdentityFilter(client_id=client_id, **data.dict())
        db.add(f)

    db.commit()
    db.refresh(f)
    return f


@router.put("/{client_id}", response_model=IdentityFilterOut)
def update_identity_filter(client_id: int, data: IdentityFilterCreate, db: Session = Depends(get_db)):
    f = db.query(IdentityFilter).filter(IdentityFilter.client_id == client_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="No identity filter found. Use POST to create.")

    for key, val in data.dict(exclude_unset=True).items():
        setattr(f, key, val)

    db.commit()
    db.refresh(f)
    return f
