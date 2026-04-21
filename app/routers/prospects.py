import csv
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import Prospect
from app.schemas import ProspectCreate, ProspectOut, BulkProspectCreate

router = APIRouter(prefix="/api/prospects", tags=["prospects"])


@router.get("/", response_model=List[ProspectOut])
def list_prospects(
    search: Optional[str] = None,
    type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Prospect)
    if search:
        q = q.filter(Prospect.name.ilike(f"%{search}%"))
    if type:
        q = q.filter(Prospect.type == type)
    return q.order_by(Prospect.name).all()


@router.post("/", response_model=ProspectOut)
def create_prospect(data: ProspectCreate, db: Session = Depends(get_db)):
    prospect = Prospect(**data.dict())
    db.add(prospect)
    db.commit()
    db.refresh(prospect)
    return prospect


@router.post("/bulk", response_model=List[ProspectOut])
def bulk_create_prospects(data: BulkProspectCreate, db: Session = Depends(get_db)):
    """Create prospects from a list of company names. Skips duplicates."""
    created = []
    for name in data.names:
        name = name.strip()
        if not name:
            continue
        existing = db.query(Prospect).filter(Prospect.name.ilike(name)).first()
        if existing:
            created.append(existing)
            continue
        prospect = Prospect(name=name)
        db.add(prospect)
        db.flush()
        created.append(prospect)
    db.commit()
    for p in created:
        db.refresh(p)
    return created


@router.post("/import-csv")
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Import prospects from CSV. Expected columns:
    Partner Name, Partner Type, Region, Tier (Guidewire format)
    OR: name, type, domain, hq_city, hq_state
    """
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    skipped = 0
    for row in reader:
        # Support both Guidewire format and generic format
        name = row.get("Partner Name") or row.get("name") or ""
        name = name.strip()
        if not name:
            continue

        existing = db.query(Prospect).filter(Prospect.name.ilike(name)).first()
        if existing:
            skipped += 1
            continue

        prospect = Prospect(
            name=name,
            type=row.get("Partner Type") or row.get("type"),
            domain=row.get("domain"),
            hq_city=row.get("hq_city"),
            hq_state=row.get("hq_state"),
        )
        db.add(prospect)
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped}


@router.get("/{prospect_id}", response_model=ProspectOut)
def get_prospect(prospect_id: int, db: Session = Depends(get_db)):
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return prospect


@router.put("/{prospect_id}", response_model=ProspectOut)
def update_prospect(prospect_id: int, data: ProspectCreate, db: Session = Depends(get_db)):
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    for key, val in data.dict(exclude_unset=True).items():
        setattr(prospect, key, val)
    db.commit()
    db.refresh(prospect)
    return prospect
