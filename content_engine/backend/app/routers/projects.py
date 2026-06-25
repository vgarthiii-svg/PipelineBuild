"""Content projects + the core workflow: research -> generate -> (score)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, provider
from ..engines import generation, research
from ..engines.platform_rules import find_rule
from ..models import (
    BrandProfile,
    ContentDraft,
    ContentProject,
    PlatformRule,
    ResearchBrief,
    ResearchSource,
    User,
)
from ..schemas import DraftOut, ProjectIn, ProjectOut, ResearchOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


# --- helpers ---------------------------------------------------------------
def _project_dict(p: ContentProject) -> dict:
    return {
        "title": p.title, "campaign": p.campaign, "platform": p.platform,
        "content_type": p.content_type, "objective": p.objective,
        "target_audience": p.target_audience, "business_goal": p.business_goal,
        "funnel_stage": p.funnel_stage, "tone": p.tone, "cta": p.cta, "length": p.length,
        "keywords": p.keywords, "offer": p.offer, "industry": p.industry,
        "competitors": p.competitors, "geo_market": p.geo_market,
        "compliance": p.compliance, "desired_outcome": p.desired_outcome,
    }


def _brand_dict(b: BrandProfile | None) -> dict | None:
    if not b:
        return None
    return {
        "company_name": b.company_name, "website": b.website, "industry": b.industry,
        "audience": b.audience, "products_services": b.products_services,
        "brand_voice": b.brand_voice, "words_to_use": b.words_to_use,
        "words_to_avoid": b.words_to_avoid, "competitors": b.competitors,
        "differentiators": b.differentiators, "proof_points": b.proof_points,
        "offers": b.offers, "compliance_rules": b.compliance_rules,
        "preferred_cta_language": b.preferred_cta_language,
        "approved_boilerplate": b.approved_boilerplate,
        "style_preferences": b.style_preferences,
    }


def _rule_dict(db: Session, platform: str, content_type: str) -> dict | None:
    # Prefer an exact platform+type match, else any rule for the content type.
    rule = db.scalar(
        select(PlatformRule).where(
            PlatformRule.platform == platform, PlatformRule.content_type == content_type
        )
    ) or db.scalar(
        select(PlatformRule).where(PlatformRule.content_type == content_type)
    )
    if rule:
        return {"label": rule.label, "structure": rule.structure,
                "best_practices": rule.best_practices, "constraints": rule.constraints}
    return find_rule(platform, content_type)


def _get_owned(db: Session, user: User, project_id: int) -> ContentProject:
    p = db.get(ContentProject, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Project not found")
    return p


def _latest_brief(db: Session, project_id: int) -> ResearchBrief | None:
    return db.scalar(
        select(ResearchBrief).where(ResearchBrief.project_id == project_id)
        .order_by(ResearchBrief.generated_at.desc())
    )


def _brief_dict(b: ResearchBrief | None) -> dict | None:
    if not b:
        return None
    return {
        "trends": b.trends, "high_performing_patterns": b.high_performing_patterns,
        "common_hooks": b.common_hooks, "audience_pain_points": b.audience_pain_points,
        "content_gaps": b.content_gaps, "recommended_angle": b.recommended_angle,
        "recommended_hook": b.recommended_hook, "keywords": b.keywords,
    }


# --- CRUD ------------------------------------------------------------------
@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(
        select(ContentProject).where(ContentProject.user_id == user.id)
        .order_by(ContentProject.updated_at.desc())
    ).all()


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    p = ContentProject(user_id=user.id, **payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned(db, user, project_id)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, payload: ProjectIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    p = _get_owned(db, user, project_id)
    for k, v in payload.model_dump().items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = _get_owned(db, user, project_id)
    db.delete(p)
    db.commit()


# --- Workflow: research ----------------------------------------------------
@router.post("/{project_id}/research", response_model=ResearchOut)
def run_research(project_id: int, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    p = _get_owned(db, user, project_id)
    brand = db.get(BrandProfile, p.brand_id) if p.brand_id else None
    data = research.run_research(provider=provider(), project=_project_dict(p),
                                 brand=_brand_dict(brand))
    sources = data.pop("sources", [])
    brief = ResearchBrief(project_id=p.id, **data)
    db.add(brief)
    db.flush()
    for s in sources:
        db.add(ResearchSource(brief_id=brief.id, title=s["title"], url=s["url"],
                              snippet=s["snippet"], source_type=s["source_type"]))
    if p.status == "idea":
        p.status = "researching"
    db.commit()
    db.refresh(brief)
    return brief


@router.get("/{project_id}/research", response_model=ResearchOut | None)
def get_research(project_id: int, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    _get_owned(db, user, project_id)
    return _latest_brief(db, project_id)


# --- Workflow: generate draft ----------------------------------------------
@router.post("/{project_id}/generate", response_model=DraftOut)
def generate(project_id: int, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    p = _get_owned(db, user, project_id)
    brand = db.get(BrandProfile, p.brand_id) if p.brand_id else None
    rule = _rule_dict(db, p.platform, p.content_type)
    brief = _latest_brief(db, p.id)

    data = generation.generate_draft(
        provider=provider(), project=_project_dict(p), brand=_brand_dict(brand),
        rule=rule, brief=_brief_dict(brief),
    )
    last = db.scalar(
        select(ContentDraft).where(ContentDraft.project_id == p.id)
        .order_by(ContentDraft.version.desc())
    )
    version = (last.version + 1) if last else 1

    draft = ContentDraft(project_id=p.id, version=version, **data)
    db.add(draft)
    if p.status in ("idea", "researching"):
        p.status = "drafted"
    db.commit()
    db.refresh(draft)
    return draft


@router.get("/{project_id}/drafts", response_model=list[DraftOut])
def list_drafts(project_id: int, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    _get_owned(db, user, project_id)
    return db.scalars(
        select(ContentDraft).where(ContentDraft.project_id == project_id)
        .order_by(ContentDraft.version.desc())
    ).all()
