"""Content library — search, filter, and browse all drafts with metadata."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ContentDraft, ContentProject, Score, User

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("")
def library(
    q: str | None = None,
    platform: str | None = None,
    content_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(ContentDraft, ContentProject)
        .join(ContentProject, ContentDraft.project_id == ContentProject.id)
        .where(ContentProject.user_id == user.id)
    )
    if platform:
        stmt = stmt.where(ContentProject.platform == platform)
    if content_type:
        stmt = stmt.where(ContentProject.content_type == content_type)
    if status:
        stmt = stmt.where(ContentProject.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(ContentDraft.title.ilike(like), ContentDraft.body.ilike(like),
                             ContentProject.title.ilike(like), ContentProject.campaign.ilike(like)))
    stmt = stmt.order_by(ContentDraft.created_at.desc())

    rows = db.execute(stmt).all()
    items = []
    for draft, project in rows:
        latest = db.scalar(
            select(Score).where(Score.draft_id == draft.id).order_by(Score.created_at.desc())
        )
        items.append({
            "draft_id": draft.id, "project_id": project.id,
            "title": draft.title or project.title, "brand_id": project.brand_id,
            "platform": project.platform, "content_type": project.content_type,
            "campaign": project.campaign, "status": project.status,
            "version": draft.version, "is_final": draft.is_final,
            "score": latest.overall if latest else None,
            "target_audience": project.target_audience, "cta": project.cta,
            "tags": [t.name for t in draft.tags],
            "created_at": draft.created_at,
        })
    return {"count": len(items), "items": items}
