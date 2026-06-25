"""Admin/Settings: platform rules, style-guide rules, saved snippets,
app settings, and the standalone AP-style checker."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..engines import ap_style
from ..models import AppSetting, PlatformRule, SavedSnippet, StyleGuideRule, User
from ..schemas import SettingIn, SnippetIn, StyleRuleIn

router = APIRouter(prefix="/api/settings", tags=["settings"])


# --- Platform rules --------------------------------------------------------
@router.get("/platform-rules")
def list_platform_rules(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.scalars(select(PlatformRule).order_by(PlatformRule.content_type)).all()
    return [{"id": r.id, "platform": r.platform, "content_type": r.content_type,
             "label": r.label, "structure": r.structure, "best_practices": r.best_practices,
             "constraints": r.constraints, "is_system": r.is_system} for r in rows]


@router.put("/platform-rules/{rule_id}")
def update_platform_rule(rule_id: int, payload: dict, db: Session = Depends(get_db),
                         _: User = Depends(get_current_user)):
    rule = db.get(PlatformRule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    for k in ("label", "structure", "best_practices", "constraints"):
        if k in payload:
            setattr(rule, k, payload[k])
    db.commit()
    return {"id": rule.id}


# --- Style-guide rules -----------------------------------------------------
@router.get("/style-rules")
def list_style_rules(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(
        select(StyleGuideRule).where(
            or_(StyleGuideRule.is_system.is_(True), StyleGuideRule.user_id == user.id)
        )
    ).all()
    return [{"id": r.id, "name": r.name, "category": r.category, "rule": r.rule,
             "detection": r.detection, "severity": r.severity, "is_system": r.is_system,
             "enabled": r.enabled, "brand_id": r.brand_id} for r in rows]


@router.post("/style-rules", status_code=201)
def create_style_rule(payload: StyleRuleIn, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    rule = StyleGuideRule(user_id=user.id, is_system=False, **payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"id": rule.id}


@router.put("/style-rules/{rule_id}")
def update_style_rule(rule_id: int, payload: StyleRuleIn, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    rule = db.get(StyleGuideRule, rule_id)
    if not rule or (not rule.is_system and rule.user_id != user.id):
        raise HTTPException(404, "Rule not found")
    if rule.is_system:
        raise HTTPException(400, "System rules can only be toggled, not edited")
    for k, v in payload.model_dump().items():
        setattr(rule, k, v)
    db.commit()
    return {"id": rule.id}


@router.post("/style-rules/{rule_id}/toggle")
def toggle_style_rule(rule_id: int, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    rule = db.get(StyleGuideRule, rule_id)
    if not rule or (not rule.is_system and rule.user_id != user.id):
        raise HTTPException(404, "Rule not found")
    rule.enabled = not rule.enabled
    db.commit()
    return {"id": rule.id, "enabled": rule.enabled}


@router.delete("/style-rules/{rule_id}", status_code=204)
def delete_style_rule(rule_id: int, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    rule = db.get(StyleGuideRule, rule_id)
    if not rule or rule.user_id != user.id or rule.is_system:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()


# --- AP-style checker (standalone) -----------------------------------------
@router.post("/ap-check")
def ap_check(payload: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    text = payload.get("text", "")
    custom = db.scalars(
        select(StyleGuideRule).where(
            StyleGuideRule.enabled.is_(True),
            or_(StyleGuideRule.is_system.is_(True), StyleGuideRule.user_id == user.id),
        )
    ).all()
    rules = [{"name": r.name, "category": r.category, "severity": r.severity,
              "rule": r.rule, "detection": r.detection} for r in custom]
    return ap_style.check(text, rules)


# --- Saved snippets (CTAs/offers/audiences/compliance) ---------------------
@router.get("/snippets")
def list_snippets(kind: str | None = None, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    stmt = select(SavedSnippet).where(SavedSnippet.user_id == user.id)
    if kind:
        stmt = stmt.where(SavedSnippet.kind == kind)
    rows = db.scalars(stmt.order_by(SavedSnippet.kind, SavedSnippet.label)).all()
    return [{"id": r.id, "kind": r.kind, "label": r.label, "value": r.value} for r in rows]


@router.post("/snippets", status_code=201)
def create_snippet(payload: SnippetIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    s = SavedSnippet(user_id=user.id, **payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id}


@router.delete("/snippets/{snippet_id}", status_code=204)
def delete_snippet(snippet_id: int, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    s = db.get(SavedSnippet, snippet_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Snippet not found")
    db.delete(s)
    db.commit()


# --- App settings (key/value) ----------------------------------------------
@router.get("/app")
def get_app_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(AppSetting).where(AppSetting.user_id == user.id)).all()
    return {r.key: r.value for r in rows}


@router.put("/app")
def set_app_setting(payload: SettingIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    row = db.scalar(
        select(AppSetting).where(AppSetting.user_id == user.id, AppSetting.key == payload.key)
    )
    if row:
        row.value = payload.value
    else:
        db.add(AppSetting(user_id=user.id, key=payload.key, value=payload.value))
    db.commit()
    return {"key": payload.key, "value": payload.value}
