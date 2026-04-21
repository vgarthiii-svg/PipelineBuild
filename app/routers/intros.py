import json
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import IntroPackage, PipelineEntry, Prospect, Client, Relationship, ActivityLog
from app.schemas import IntroPackageOut, IntroPackageUpdate

router = APIRouter(prefix="/api/intros", tags=["intros"])


@router.post("/generate/{entry_id}", response_model=IntroPackageOut)
def generate_intro(entry_id: int, db: Session = Depends(get_db)):
    """Generate an intro package for a pipeline entry using Claude API."""
    entry = db.query(PipelineEntry).filter(PipelineEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Pipeline entry not found")

    prospect = db.query(Prospect).filter(Prospect.id == entry.prospect_id).first()
    client = db.query(Client).filter(Client.id == entry.client_id).first()
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

    # Try Claude API if key is set
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

    # Save the package
    pkg = IntroPackage(
        pipeline_entry_id=entry_id,
        target_contact=contact_name,
        target_title=contact_title,
        email_subject=package_data.get("email_subject", f"Quick intro: {client.name} x {prospect.name}"),
        email_body=package_data.get("email_body", ""),
        talking_points=json.dumps(package_data.get("talking_points", [])),
        value_prop_prospect=package_data.get("value_prop_prospect", ""),
        value_prop_client=package_data.get("value_prop_client", ""),
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
    """Generate a template intro package when Claude API is not available."""
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
        "value_prop_prospect": f"Access to {client.name}'s capabilities in {client.primary_revenue_driver or 'their space'}",
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

        # Update pipeline entry status
        entry = db.query(PipelineEntry).filter(PipelineEntry.id == pkg.pipeline_entry_id).first()
        if entry:
            entry.status = "outreach_sent"
            entry.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(pkg)
    return pkg
