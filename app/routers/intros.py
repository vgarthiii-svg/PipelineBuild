import json
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import IntroPackage, PipelineEntry, Prospect, Client, Relationship, ActivityLog
from app.schemas import IntroPackageOut, IntroPackageUpdate

router = APIRouter(prefix="/api/intros", tags=["intros"])


@router.post("/generate/{entry_id}")
def generate_intro(entry_id: int, force: bool = False, contact_name: str = None, db: Session = Depends(get_db)):
    """
    Generate an intro package. If Claude API key is set and force=False,
    queues a pending action for user approval. If force=True, executes immediately.
    contact_name (optional): target a specific contact instead of highest-RS contact.
    """
    entry = db.query(PipelineEntry).filter(PipelineEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Pipeline entry not found")

    prospect = db.query(Prospect).filter(Prospect.id == entry.prospect_id).first()
    client = db.query(Client).filter(Client.id == entry.client_id).first()

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    # If API key is set and not forced, queue for approval
    if api_key and not force:
        from app.routers.notifications import create_pending_action
        action = create_pending_action(
            db,
            action_type="generate_intro",
            description=f"Generate AI-written intro email for {contact_name or 'best contact'} at {prospect.name} (client: {client.name}). Claude API will research and write a personalized outreach email.",
            params={"entry_id": entry_id, "contact_name": contact_name},
            estimated_cost="$0.02-0.05",
        )
        return {
            "status": "pending_approval",
            "action_id": action.id,
            "message": f"Intro generation for {prospect.name} requires your approval. Check the notification bar.",
        }

    # Execute
    return _do_generate_intro(entry_id, db, contact_name=contact_name)


def _do_generate_intro(entry_id, db, contact_name=None):
    """Actually generate the intro package."""
    entry = db.query(PipelineEntry).filter(PipelineEntry.id == entry_id).first()
    if not entry:
        return {"error": "Entry not found"}

    prospect = db.query(Prospect).filter(Prospect.id == entry.prospect_id).first()
    client = db.query(Client).filter(Client.id == entry.client_id).first()

    # If contact_name specified, find that specific person. Otherwise highest-scored.
    if contact_name:
        best_rel = (
            db.query(Relationship)
            .filter(Relationship.prospect_id == entry.prospect_id,
                    Relationship.contact_name.ilike(f"%{contact_name}%"))
            .first()
        )
    else:
        best_rel = (
            db.query(Relationship)
            .filter(Relationship.prospect_id == entry.prospect_id)
            .order_by(Relationship.score.desc())
            .first()
        )

    contact_name = best_rel.contact_name if best_rel else "the team"
    contact_title = best_rel.contact_title if best_rel else ""
    warmest_path = best_rel.warmest_path if best_rel else "Cold outreach"
    rel_context = best_rel.context if best_rel else "No existing relationship"

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            from app.services.claude_ai import generate_intro_package
            package_data = generate_intro_package(
                prospect_name=prospect.name,
                prospect_description=prospect.description or prospect.type or "",
                client_name=client.name,
                client_description=client.description or "",
                client_key_stat=client.primary_revenue_driver or "",
                contact_name=contact_name,
                contact_title=contact_title,
                relationship_context=rel_context,
                fit_reasoning=f"Matchmaker Score: {entry.matchmaker_score}, PMF: {entry.pmf_score}",
            )
        except Exception as e:
            package_data = _fallback_package(prospect, client, contact_name, contact_title, warmest_path, rel_context)
    else:
        package_data = _fallback_package(prospect, client, contact_name, contact_title, warmest_path, rel_context)

    def _to_str(val, default=""):
        """Coerce any Claude response value into a SQLite-safe string."""
        if val is None:
            return default
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            # Concatenate dict values readably
            parts = [f"{k}: {v}" for k, v in val.items() if v]
            return " | ".join(parts) if parts else default
        if isinstance(val, list):
            return ", ".join(str(v) for v in val) if val else default
        return str(val)

    pkg = IntroPackage(
        pipeline_entry_id=entry_id,
        target_contact=_to_str(contact_name),
        target_title=_to_str(contact_title),
        email_subject=_to_str(package_data.get("email_subject"), f"Quick intro: {client.name} x {prospect.name}"),
        email_body=_to_str(package_data.get("email_body")),
        talking_points=json.dumps(package_data.get("talking_points", [])),
        value_prop_prospect=_to_str(package_data.get("value_prop_prospect")),
        value_prop_client=_to_str(package_data.get("value_prop_client")),
        mutual_connections=json.dumps(package_data.get("mutual_connections", [])),
        objections_json=json.dumps(package_data.get("objections", [])),
        status="draft",
    )
    db.add(pkg)

    log = ActivityLog(
        pipeline_entry_id=entry_id,
        action="intro_generated",
        new_value=f"Intro package created for {contact_name} at {prospect.name}",
    )
    db.add(log)
    db.commit()
    db.refresh(pkg)
    return pkg


def _fallback_package(prospect, client, contact_name, contact_title, warmest_path, rel_context):
    return {
        "email_subject": f"Quick intro: {client.name} + {prospect.name}",
        "email_body": (
            f"Hi {contact_name},\n\n"
            f"I work with {client.name} and wanted to connect you two. "
            f"{client.description or 'They have a product I think would be relevant to your team.'}\n\n"
            f"{'I thought of you because ' + rel_context + '.' if rel_context != 'No existing relationship' else 'I came across ' + prospect.name + ' and saw a strong fit.'}\n\n"
            f"Worth a 15-minute call to explore?\n\n"
            f"Best,\nVinnie"
        ),
        "talking_points": [
            f"Discuss how {client.name} aligns with {prospect.name}'s distribution needs",
            f"Reference {client.primary_revenue_driver or 'their core offering'} as the value driver",
            f"Connection path: {warmest_path}",
        ],
        "value_prop_prospect": f"Access to {client.name}'s capabilities",
        "value_prop_client": f"Potential distribution partnership with {prospect.name}",
        "mutual_connections": [warmest_path] if warmest_path != "Cold outreach" else [],
        "objections": [
            {"objection": "We already have a solution for this", "response": f"Totally get it. Most of {client.name}'s partners said the same thing initially. The difference is [specific differentiator]. Worth a quick look?"},
            {"objection": "Not a priority right now", "response": "Fair enough. Can I send over a one-pager so it's on your radar when timing is better?"},
        ],
    }


@router.get("/{entry_id}", response_model=IntroPackageOut)
def get_intro(entry_id: int, db: Session = Depends(get_db)):
    pkg = (
        db.query(IntroPackage)
        .filter(IntroPackage.pipeline_entry_id == entry_id)
        .order_by(IntroPackage.created_at.desc())
        .first()
    )
    if not pkg:
        raise HTTPException(status_code=404, detail="No intro package found")
    return pkg


@router.put("/{package_id}", response_model=IntroPackageOut)
def update_intro(package_id: int, data: IntroPackageUpdate, db: Session = Depends(get_db)):
    pkg = db.query(IntroPackage).filter(IntroPackage.id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Intro package not found")

    for key, val in data.dict(exclude_unset=True).items():
        if val is not None:
            setattr(pkg, key, val)

    if data.status == "sent":
        pkg.sent_date = datetime.utcnow()
        log = ActivityLog(
            pipeline_entry_id=pkg.pipeline_entry_id,
            action="intro_sent",
            new_value=f"Intro sent to {pkg.target_contact}",
        )
        db.add(log)
        entry = db.query(PipelineEntry).filter(PipelineEntry.id == pkg.pipeline_entry_id).first()
        if entry:
            entry.status = "outreach_sent"
            entry.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(pkg)
    return pkg
