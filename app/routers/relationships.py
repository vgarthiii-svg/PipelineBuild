import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import (
    Relationship, RelationshipScan, Prospect, PipelineEntry,
    ConferenceAttendee, ActivityLog,
)
from app.schemas import RelationshipCreate, RelationshipOut
from app.scoring import calculate_matchmaker, assign_tier

router = APIRouter(prefix="/api/relationships", tags=["relationships"])


@router.get("/{prospect_id}", response_model=List[RelationshipOut])
def get_relationships(prospect_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Relationship)
        .filter(Relationship.prospect_id == prospect_id)
        .order_by(Relationship.score.desc())
        .all()
    )


@router.post("/", response_model=RelationshipOut)
def create_or_update_relationship(data: RelationshipCreate, db: Session = Depends(get_db)):
    # Check if relationship already exists for this prospect + contact
    existing = None
    if data.contact_name:
        existing = (
            db.query(Relationship)
            .filter(
                Relationship.prospect_id == data.prospect_id,
                Relationship.contact_name == data.contact_name,
            )
            .first()
        )

    if existing:
        old_score = existing.score
        for key, val in data.dict(exclude_unset=True).items():
            setattr(existing, key, val)
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        rel = existing
    else:
        rel = Relationship(**data.dict())
        db.add(rel)
        db.commit()
        db.refresh(rel)
        old_score = 0

    # Update pipeline entries for this prospect
    _sync_rs_to_pipeline(data.prospect_id, db, old_score)

    return rel


@router.put("/{relationship_id}", response_model=RelationshipOut)
def update_relationship(relationship_id: int, data: RelationshipCreate, db: Session = Depends(get_db)):
    rel = db.query(Relationship).filter(Relationship.id == relationship_id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")

    old_score = rel.score
    for key, val in data.dict(exclude_unset=True).items():
        setattr(rel, key, val)
    rel.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rel)

    _sync_rs_to_pipeline(rel.prospect_id, db, old_score)
    return rel


def _sync_rs_to_pipeline(prospect_id: int, db: Session, old_score: int = 0):
    """When a relationship changes, update all pipeline entries for this prospect."""
    best_rel = (
        db.query(Relationship)
        .filter(Relationship.prospect_id == prospect_id)
        .order_by(Relationship.score.desc())
        .first()
    )
    new_rs = best_rel.score if best_rel else 0

    entries = db.query(PipelineEntry).filter(PipelineEntry.prospect_id == prospect_id).all()
    for entry in entries:
        if entry.relationship_score != new_rs:
            old_tier = entry.tier
            entry.relationship_score = new_rs
            pmf = entry.pmf_score or 0.0
            entry.matchmaker_score = round(
                calculate_matchmaker(pmf, new_rs, entry.pmf_weight, entry.rs_weight), 1
            )
            entry.tier = assign_tier(entry.matchmaker_score)
            entry.updated_at = datetime.utcnow()

            log = ActivityLog(
                pipeline_entry_id=entry.id,
                action="relationship_updated",
                old_value=str(old_score),
                new_value=str(new_rs),
                notes=f"Tier: {old_tier} -> {entry.tier}" if old_tier != entry.tier else None,
            )
            db.add(log)

    db.commit()


@router.post("/{prospect_id}/scan")
def scan_relationships(prospect_id: int, db: Session = Depends(get_db)):
    """
    Run a relationship scan using available sources.
    Currently checks: conference_attendees table and relationships table.
    Gmail, HubSpot, Calendar scans activate when API keys are configured.
    """
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    scan = RelationshipScan(prospect_id=prospect_id)

    # Source 4: Conference attendees
    attendees = (
        db.query(ConferenceAttendee)
        .filter(ConferenceAttendee.company.ilike(f"%{prospect.name}%"))
        .all()
    )
    if attendees:
        scan.conference_hits = len(attendees)
        scan.conference_details = json.dumps([
            {
                "attendee_name": a.attendee_name,
                "title": a.title,
                "conference_name": a.conference_name,
            }
            for a in attendees
        ])

    # Source 5: Existing relationships
    rels = (
        db.query(Relationship)
        .filter(Relationship.prospect_id == prospect_id)
        .all()
    )
    if rels:
        scan.relationship_map_hits = len(rels)
        scan.relationship_map_details = json.dumps([
            {
                "contact_name": r.contact_name,
                "score": r.score,
                "context": r.context,
                "warmest_path": r.warmest_path,
            }
            for r in rels
        ])

    # Sources 1-3: Stubs (Gmail, HubSpot, Calendar)
    # These will be populated when API integrations are configured
    scan.gmail_hits = 0
    scan.gmail_details = json.dumps([])
    scan.hubspot_hits = 0
    scan.hubspot_details = json.dumps([])
    scan.calendar_hits = 0
    scan.calendar_details = json.dumps([])

    # Calculate final RS from evidence
    total_hits = (
        scan.gmail_hits + scan.hubspot_hits + scan.calendar_hits
        + scan.conference_hits + scan.relationship_map_hits
    )
    if rels:
        scan.final_rs = max(r.score for r in rels)
    elif scan.conference_hits > 0:
        scan.final_rs = 1
    else:
        scan.final_rs = 0

    scan.evidence_summary = _build_evidence_summary(scan)

    db.add(scan)
    db.commit()
    db.refresh(scan)

    return {
        "scan_id": scan.id,
        "prospect_name": prospect.name,
        "gmail_hits": scan.gmail_hits,
        "hubspot_hits": scan.hubspot_hits,
        "calendar_hits": scan.calendar_hits,
        "conference_hits": scan.conference_hits,
        "relationship_map_hits": scan.relationship_map_hits,
        "final_rs": scan.final_rs,
        "evidence_summary": scan.evidence_summary,
    }


def _build_evidence_summary(scan: RelationshipScan) -> str:
    parts = []
    if scan.gmail_hits:
        parts.append(f"Gmail: {scan.gmail_hits} threads")
    if scan.hubspot_hits:
        parts.append(f"HubSpot: {scan.hubspot_hits} records")
    if scan.calendar_hits:
        parts.append(f"Calendar: {scan.calendar_hits} events")
    if scan.conference_hits:
        details = json.loads(scan.conference_details) if scan.conference_details else []
        names = [d.get("attendee_name", "") for d in details]
        parts.append(f"Conference: {', '.join(names)}")
    if scan.relationship_map_hits:
        details = json.loads(scan.relationship_map_details) if scan.relationship_map_details else []
        contacts = [f"{d.get('contact_name', '')} (RS:{d.get('score', 0)})" for d in details]
        parts.append(f"Relationship Map: {', '.join(contacts)}")

    if not parts:
        return "No evidence found across any source."

    return " | ".join(parts)


@router.get("/scans/{prospect_id}")
def get_scan_history(prospect_id: int, db: Session = Depends(get_db)):
    scans = (
        db.query(RelationshipScan)
        .filter(RelationshipScan.prospect_id == prospect_id)
        .order_by(RelationshipScan.scan_date.desc())
        .all()
    )
    return [
        {
            "scan_id": s.id,
            "scan_date": s.scan_date,
            "gmail_hits": s.gmail_hits,
            "hubspot_hits": s.hubspot_hits,
            "calendar_hits": s.calendar_hits,
            "conference_hits": s.conference_hits,
            "relationship_map_hits": s.relationship_map_hits,
            "final_rs": s.final_rs,
            "evidence_summary": s.evidence_summary,
        }
        for s in scans
    ]
