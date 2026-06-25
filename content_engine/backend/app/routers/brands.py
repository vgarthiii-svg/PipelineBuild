"""Brand profile CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import BrandProfile, User
from ..schemas import BrandIn, BrandOut

router = APIRouter(prefix="/api/brands", tags=["brands"])


@router.get("", response_model=list[BrandOut])
def list_brands(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(
        select(BrandProfile).where(BrandProfile.user_id == user.id).order_by(BrandProfile.name)
    ).all()


@router.post("", response_model=BrandOut, status_code=201)
def create_brand(payload: BrandIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    brand = BrandProfile(user_id=user.id, **payload.model_dump())
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


def _get_owned(db: Session, user: User, brand_id: int) -> BrandProfile:
    brand = db.get(BrandProfile, brand_id)
    if not brand or brand.user_id != user.id:
        raise HTTPException(404, "Brand not found")
    return brand


@router.get("/{brand_id}", response_model=BrandOut)
def get_brand(brand_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned(db, user, brand_id)


@router.put("/{brand_id}", response_model=BrandOut)
def update_brand(brand_id: int, payload: BrandIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    brand = _get_owned(db, user, brand_id)
    for k, v in payload.model_dump().items():
        setattr(brand, k, v)
    db.commit()
    db.refresh(brand)
    return brand


@router.delete("/{brand_id}", status_code=204)
def delete_brand(brand_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    brand = _get_owned(db, user, brand_id)
    db.delete(brand)
    db.commit()
