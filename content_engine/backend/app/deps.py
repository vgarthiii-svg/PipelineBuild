"""Shared FastAPI dependencies: current user + provider access.

Auth seam: in single-user mode a default user is auto-provisioned and used for
every request. To integrate Clerk/Supabase/Auth0, replace `get_current_user`
to resolve the user from a verified JWT (the rest of the app is unchanged).
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .ai.provider import AIProvider, get_ai_provider
from .config import settings
from .database import get_db
from .models import User


def get_current_user(
    db: Session = Depends(get_db),
    x_user_email: str | None = Header(default=None),
) -> User:
    email = x_user_email or (settings.default_user_email if settings.single_user_mode else None)
    if not email:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        if not settings.single_user_mode and x_user_email is None:
            raise HTTPException(status_code=401, detail="Unknown user")
        user = User(email=email, name=email.split("@")[0])
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def provider() -> AIProvider:
    return get_ai_provider()
