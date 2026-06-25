"""Draft-level operations: score, revise, repurpose, export, finalize, tag."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, provider
from ..engines import export as export_engine
from ..engines import generation, repurpose, scoring
from ..models import (
    BrandProfile,
    ContentDraft,
    ContentProject,
    ExportHistory,
    RevisionHistory,
    Score,
    StyleGuideRule,
    Tag,
    User,
)
from ..schemas import DraftOut, RepurposeIn, ReviseIn, ScoreOut, TagIn
from .projects import _brand_dict, _project_dict

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


def _get_owned_draft(db: Session, user: User, draft_id: int) -> tuple[ContentDraft, ContentProject]:
    draft = db.get(ContentDraft, draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    project = db.get(ContentProject, draft.project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(404, "Draft not found")
    return draft, project


def _custom_style_rules(db: Session, user: User, brand_id: int | None) -> list[dict]:
    rules = db.scalars(
        select(StyleGuideRule).where(
            StyleGuideRule.enabled.is_(True),
            or_(
                StyleGuideRule.is_system.is_(True),
                StyleGuideRule.user_id == user.id,
            ),
        )
    ).all()
    return [{"name": r.name, "category": r.category, "severity": r.severity,
             "rule": r.rule, "detection": r.detection} for r in rules
            if r.brand_id in (None, brand_id)]


@router.get("/{draft_id}", response_model=DraftOut)
def get_draft(draft_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    draft, _ = _get_owned_draft(db, user, draft_id)
    return draft


@router.put("/{draft_id}/body", response_model=DraftOut)
def update_body(draft_id: int, payload: dict, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    """Persist manual edits from the draft editor."""
    draft, _ = _get_owned_draft(db, user, draft_id)
    if "body" in payload:
        draft.body = payload["body"]
    if "title" in payload:
        draft.title = payload["title"]
    db.commit()
    db.refresh(draft)
    return draft


# --- Score -----------------------------------------------------------------
@router.post("/{draft_id}/score", response_model=ScoreOut)
def score(draft_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    draft, project = _get_owned_draft(db, user, draft_id)
    brand = db.get(BrandProfile, project.brand_id) if project.brand_id else None
    result = scoring.score_draft(
        provider=provider(), draft_body=draft.body, project=_project_dict(project),
        brand=_brand_dict(brand),
        custom_style_rules=_custom_style_rules(db, user, project.brand_id),
    )
    row = Score(draft_id=draft.id, overall=result["overall"],
                categories=result["categories"], summary=result["summary"])
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{draft_id}/score", response_model=ScoreOut | None)
def latest_score(draft_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_owned_draft(db, user, draft_id)
    return db.scalar(select(Score).where(Score.draft_id == draft_id).order_by(Score.created_at.desc()))


# --- Revise ----------------------------------------------------------------
@router.post("/{draft_id}/revise", response_model=DraftOut)
def revise(draft_id: int, payload: ReviseIn, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    draft, project = _get_owned_draft(db, user, draft_id)
    brand = db.get(BrandProfile, project.brand_id) if project.brand_id else None
    before = payload.body if payload.body is not None else draft.body
    after = generation.revise_draft(
        provider=provider(), body=before, action=payload.action,
        instruction=payload.instruction, project=_project_dict(project), brand=_brand_dict(brand),
    )
    db.add(RevisionHistory(draft_id=draft.id, action=payload.action,
                           instruction=payload.instruction, before_text=before, after_text=after))
    draft.body = after
    db.commit()
    db.refresh(draft)
    return draft


@router.get("/{draft_id}/revisions")
def list_revisions(draft_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_owned_draft(db, user, draft_id)
    rows = db.scalars(
        select(RevisionHistory).where(RevisionHistory.draft_id == draft_id)
        .order_by(RevisionHistory.created_at.desc())
    ).all()
    return [{"id": r.id, "action": r.action, "instruction": r.instruction,
             "before_text": r.before_text, "after_text": r.after_text,
             "created_at": r.created_at} for r in rows]


# --- Repurpose -------------------------------------------------------------
@router.post("/{draft_id}/repurpose")
def repurpose_draft(draft_id: int, payload: RepurposeIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    draft, project = _get_owned_draft(db, user, draft_id)
    brand = db.get(BrandProfile, project.brand_id) if project.brand_id else None
    body = payload.body if payload.body is not None else draft.body
    outputs = repurpose.repurpose(
        provider=provider(), source_body=body, source_type=project.content_type or "post",
        targets=payload.targets, project=_project_dict(project), brand=_brand_dict(brand),
    )
    return {"outputs": outputs}


# --- Finalize / status -----------------------------------------------------
@router.post("/{draft_id}/finalize", response_model=DraftOut)
def finalize(draft_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    draft, project = _get_owned_draft(db, user, draft_id)
    draft.is_final = True
    project.status = "approved"
    db.commit()
    db.refresh(draft)
    return draft


# --- Tags ------------------------------------------------------------------
@router.post("/{draft_id}/tags", response_model=DraftOut)
def add_tag(draft_id: int, payload: TagIn, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    draft, _ = _get_owned_draft(db, user, draft_id)
    tag = db.scalar(select(Tag).where(Tag.user_id == user.id, Tag.name == payload.name))
    if not tag:
        tag = Tag(user_id=user.id, name=payload.name, color=payload.color)
        db.add(tag)
        db.flush()
    if tag not in draft.tags:
        draft.tags.append(tag)
    db.commit()
    db.refresh(draft)
    return draft


# --- Export ----------------------------------------------------------------
def _draft_payload(draft: ContentDraft) -> dict:
    return {"title": draft.title, "body": draft.body,
            "headline_options": draft.headline_options, "cta_options": draft.cta_options,
            "rationale": draft.rationale, "posting_guidance": draft.posting_guidance}


@router.get("/{draft_id}/export/{fmt}")
def export_draft(draft_id: int, fmt: str, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    draft, _ = _get_owned_draft(db, user, draft_id)
    payload = _draft_payload(draft)
    # ASCII-only, filesystem- and header-safe filename.
    raw = (draft.title or "draft").replace(" ", "_")
    safe_title = "".join(c for c in raw if c.isalnum() or c in "_-")[:40] or "draft"

    if fmt == "docx":
        data = export_engine.to_docx_bytes(payload)
        db.add(ExportHistory(draft_id=draft.id, fmt="docx", filename=f"{safe_title}.docx"))
        db.commit()
        return StreamingResponse(
            iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.docx"'},
        )

    if fmt not in export_engine.EXPORTERS:
        raise HTTPException(400, f"Unsupported format: {fmt}")
    media_type, fn, ext = export_engine.EXPORTERS[fmt]
    content = fn(payload)
    db.add(ExportHistory(draft_id=draft.id, fmt=fmt, filename=f"{safe_title}.{ext}"))
    db.commit()
    return Response(
        content=content, media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.{ext}"'},
    )
