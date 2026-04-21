from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Client, ScoringCriterion
from app.schemas import ClientCreate, ClientOut, CriterionCreate, CriterionOut

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("/", response_model=List[ClientOut])
def list_clients(db: Session = Depends(get_db)):
    return db.query(Client).order_by(Client.name).all()


@router.post("/", response_model=ClientOut)
def create_client(data: ClientCreate, db: Session = Depends(get_db)):
    client = Client(**data.dict())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.put("/{client_id}", response_model=ClientOut)
def update_client(client_id: int, data: ClientCreate, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for key, val in data.dict(exclude_unset=True).items():
        setattr(client, key, val)
    db.commit()
    db.refresh(client)
    return client


# ---- Scoring Criteria ----

@router.get("/{client_id}/criteria", response_model=List[CriterionOut])
def list_criteria(client_id: int, db: Session = Depends(get_db)):
    return (
        db.query(ScoringCriterion)
        .filter(ScoringCriterion.client_id == client_id)
        .order_by(ScoringCriterion.sort_order)
        .all()
    )


@router.post("/{client_id}/criteria", response_model=CriterionOut)
def create_criterion(client_id: int, data: CriterionCreate, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    criterion = ScoringCriterion(client_id=client_id, **data.dict())
    db.add(criterion)
    db.commit()
    db.refresh(criterion)
    return criterion


@router.put("/{client_id}/criteria/{criterion_id}", response_model=CriterionOut)
def update_criterion(client_id: int, criterion_id: int, data: CriterionCreate, db: Session = Depends(get_db)):
    criterion = (
        db.query(ScoringCriterion)
        .filter(ScoringCriterion.id == criterion_id, ScoringCriterion.client_id == client_id)
        .first()
    )
    if not criterion:
        raise HTTPException(status_code=404, detail="Criterion not found")
    for key, val in data.dict(exclude_unset=True).items():
        setattr(criterion, key, val)
    db.commit()
    db.refresh(criterion)
    return criterion
