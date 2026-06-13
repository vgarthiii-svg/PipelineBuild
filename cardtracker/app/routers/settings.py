import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, IMAGE_DIR
from app.models import Setting, Card, ChecklistSet, ChecklistItem
from app.auth import COOKIE, COOKIE_MAX_AGE, hash_password

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULTS = {"app_name": "Card Tracker", "logo_image": ""}
_LOGO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}


class SettingsIn(BaseModel):
    app_name: Optional[str] = None
    logo_image: Optional[str] = None


class PasswordIn(BaseModel):
    password: Optional[str] = None


def _set(db: Session, key: str, value: str):
    row = db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    values = dict(DEFAULTS)
    for s in db.query(Setting).all():
        values[s.key] = s.value
    values["has_password"] = bool(values.pop("password_hash", ""))  # never expose the hash
    return values


@router.post("/password")
def set_password(payload: PasswordIn, db: Session = Depends(get_db)):
    """Set the shared password, or turn it off when blank. Keeps the caller logged in."""
    pw = (payload.password or "").strip()
    row = db.get(Setting, "password_hash")
    if not pw:
        if row:
            db.delete(row)
        db.commit()
        resp = JSONResponse({"ok": True, "has_password": False})
        resp.delete_cookie(COOKIE)
        return resp
    h = hash_password(pw)
    _set(db, "password_hash", h)
    db.commit()
    resp = JSONResponse({"ok": True, "has_password": True})
    resp.set_cookie(COOKIE, h, max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax")
    return resp


@router.post("/logo")
def upload_logo(file: UploadFile = File(...), db: Session = Depends(get_db)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _LOGO_EXT:
        ext = ".png"
    name = f"logo_{uuid.uuid4().hex}{ext}"
    with open(os.path.join(IMAGE_DIR, name), "wb") as f:
        f.write(file.file.read())
    _set(db, "logo_image", name)
    db.commit()
    return {"logo_image": name}


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
