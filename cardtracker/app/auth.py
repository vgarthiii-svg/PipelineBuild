import hashlib

from app.database import SessionLocal
from app.models import Setting

COOKIE = "ct_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def hash_password(pw: str) -> str:
    return hashlib.sha256(("cardtracker:" + pw).encode("utf-8")).hexdigest()


def get_password_hash() -> str:
    """Stored password hash, or '' when no password is set (auth disabled)."""
    db = SessionLocal()
    try:
        row = db.get(Setting, "password_hash")
        return (row.value if row else "") or ""
    finally:
        db.close()
