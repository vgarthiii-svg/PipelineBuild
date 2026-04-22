import json
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import Notification, PendingApiAction

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ---- Notifications ----

@router.get("/")
def list_notifications(unread_only: bool = False, limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(Notification).order_by(Notification.created_at.desc())
    if unread_only:
        q = q.filter(Notification.read == False)
    return q.limit(limit).all()


@router.get("/count")
def unread_count(db: Session = Depends(get_db)):
    count = db.query(Notification).filter(Notification.read == False).count()
    pending = db.query(PendingApiAction).filter(PendingApiAction.status == "pending").count()
    return {"unread": count, "pending_actions": pending}


@router.put("/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.id == notification_id).first()
    if n:
        n.read = True
        db.commit()
    return {"status": "ok"}


@router.put("/read-all")
def mark_all_read(db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.read == False).update({"read": True})
    db.commit()
    return {"status": "ok"}


# ---- Pending API Actions (Cost Gate) ----

@router.get("/pending")
def list_pending_actions(db: Session = Depends(get_db)):
    return (
        db.query(PendingApiAction)
        .filter(PendingApiAction.status == "pending")
        .order_by(PendingApiAction.created_at.desc())
        .all()
    )


@router.post("/pending/{action_id}/approve")
def approve_action(action_id: int, db: Session = Depends(get_db)):
    """User approves a pending API action. Executes it immediately."""
    action = db.query(PendingApiAction).filter(PendingApiAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending":
        return {"status": action.status, "message": "Already resolved"}

    action.status = "approved"
    action.resolved_at = datetime.utcnow()
    db.commit()

    # Execute the action
    result = _execute_api_action(action, db)

    action.status = "executed"
    db.commit()

    return {"status": "executed", "result": result}


@router.post("/pending/{action_id}/reject")
def reject_action(action_id: int, db: Session = Depends(get_db)):
    action = db.query(PendingApiAction).filter(PendingApiAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    action.status = "rejected"
    action.resolved_at = datetime.utcnow()
    db.commit()
    return {"status": "rejected"}


def create_pending_action(db, action_type, description, params, estimated_cost="$0.01-0.03"):
    """Helper: create a pending API action that needs user approval."""
    action = PendingApiAction(
        action_type=action_type,
        description=description,
        params_json=json.dumps(params),
        estimated_cost=estimated_cost,
    )
    db.add(action)

    # Also create a notification
    notif = Notification(
        type="api_cost_pending",
        title=f"Action requires approval: {action_type.replace('_', ' ').title()}",
        detail=f"{description} (Est. cost: {estimated_cost})",
    )
    db.add(notif)
    db.commit()
    db.refresh(action)
    return action


def _execute_api_action(action, db):
    """Execute an approved API action."""
    params = json.loads(action.params_json)

    if action.action_type == "generate_intro":
        from app.routers.intros import _do_generate_intro
        return _do_generate_intro(params.get("entry_id"), db, contact_name=params.get("contact_name"))

    elif action.action_type == "research_intent":
        from app.routers.intent import _do_research_intent
        return _do_research_intent(params.get("prospect_id"), db)

    elif action.action_type == "profile_client":
        # Deep research for a specific prospect
        prospect_id = params.get("prospect_id")
        if prospect_id:
            from app.services import profile_generator
            from app.models import Prospect, BusinessProfile
            prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
            if not prospect:
                return {"error": "Prospect not found"}

            deep_data = profile_generator.deep_research_profile(prospect)
            if deep_data.get("error"):
                return {"error": deep_data["error"]}

            # Upsert the business profile with deep data
            profile = db.query(BusinessProfile).filter(BusinessProfile.prospect_id == prospect_id).first()
            if not profile:
                profile = BusinessProfile(prospect_id=prospect_id)
                db.add(profile)

            for key, val in deep_data.items():
                if hasattr(profile, key):
                    setattr(profile, key, val)

            db.commit()
            return {"status": "success", "prospect_name": prospect.name, "confidence": deep_data.get("confidence_score", 90)}
        else:
            # Legacy path for profile_client with name/desc/domain
            from app.routers.clients import _run_claude_profiling
            name = params.get("name", "")
            desc = params.get("description", "")
            domain = params.get("domain", "")
            return _run_claude_profiling(name, desc, domain)

    return {"error": f"Unknown action type: {action.action_type}"}


def create_notification(db, type, title, detail, action_url=None):
    """Helper: create a notification."""
    n = Notification(type=type, title=title, detail=detail, action_url=action_url)
    db.add(n)
    db.commit()
    return n
