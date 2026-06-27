"""
Agent Layer API.

Exposes the scheduled_jobs registry for the dashboard: list jobs, toggle on/off,
trigger a run now, and read last-run status.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ScheduledJob
from app.services import scheduler

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _job_dict(j: ScheduledJob) -> dict:
    parsed_output = None
    if j.last_output:
        try:
            parsed_output = json.loads(j.last_output)
        except (json.JSONDecodeError, TypeError):
            parsed_output = j.last_output
    return {
        "id": j.id,
        "job_key": j.job_key,
        "name": j.name,
        "description": j.description,
        "schedule": j.schedule,
        "enabled": bool(j.enabled),
        "last_run": j.last_run.isoformat() + "Z" if j.last_run else None,
        "last_status": j.last_status,
        "last_output": parsed_output,
        "next_run": j.next_run.isoformat() if j.next_run else None,
    }


@router.get("/")
def list_jobs(db: Session = Depends(get_db)):
    """List all registered scheduled jobs with current status."""
    jobs = db.query(ScheduledJob).order_by(ScheduledJob.name).all()
    return [_job_dict(j) for j in jobs]


@router.post("/{job_key}/toggle")
def toggle_job(job_key: str, db: Session = Depends(get_db)):
    """Enable or disable a scheduled job."""
    j = db.query(ScheduledJob).filter(ScheduledJob.job_key == job_key).first()
    if not j:
        raise HTTPException(status_code=404, detail=f"Job {job_key} not found")
    j.enabled = not bool(j.enabled)
    db.commit()
    db.refresh(j)
    return _job_dict(j)


@router.post("/{job_key}/run-now")
def run_now(job_key: str):
    """Trigger a job to run immediately, outside its schedule."""
    if job_key not in scheduler.JOB_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Job {job_key} not registered")
    return scheduler.run_job(job_key)


@router.post("/sync-pipelines")
def sync_all_pipelines(db: Session = Depends(get_db)):
    """
    Manual reconciliation: ensure every client's pipeline contains every prospect
    in the system. Recovers from any drift between Layer 1 and pipeline lists.
    """
    from app.models import Prospect, Client, PipelineEntry
    from app.routers.clients import _auto_score_pipeline

    clients = db.query(Client).all()
    prospects = db.query(Prospect).all()

    total_added = 0
    added_per_client = {}
    for c in clients:
        existing = set(r[0] for r in db.query(PipelineEntry.prospect_id).filter(
            PipelineEntry.client_id == c.id
        ).all())
        count = 0
        for p in prospects:
            if p.name.lower() == c.name.lower():
                continue
            if p.id in existing:
                continue
            db.add(PipelineEntry(
                client_id=c.id,
                prospect_id=p.id,
                source="Manual pipeline sync",
            ))
            count += 1
        if count > 0:
            added_per_client[c.name] = count
            total_added += count

    db.commit()

    # Rescore active clients so newly-added rows get scores immediately
    scored = {}
    for c in clients:
        if c.active:
            scored[c.name] = _auto_score_pipeline(c.id, db)
    db.commit()

    return {
        "status": "ok",
        "added": total_added,
        "per_client": added_per_client,
        "scored": scored,
    }


# ---- Ad-hoc HubSpot import (hybrid path 2) ----

from pydantic import BaseModel


class HubSpotImportRequest(BaseModel):
    query: str


@router.post("/hubspot-import-query")
def hubspot_import_query(req: HubSpotImportRequest, db: Session = Depends(get_db)):
    """
    Pull HubSpot companies matching a free-text query (e.g. "insurance" or "agency"),
    dedupe against existing prospects/clients (including fuzzy name matches),
    import truly new ones, pull their contacts, add to all active pipelines, rescore.

    Returns a structured summary the UI can display.
    """
    from datetime import datetime
    from app.models import (Prospect, Client, PipelineEntry, Relationship,
                            BehaviorProfile)
    from app.services import hubspot_scan, type_inference, profile_generator
    from app.routers.clients import _auto_score_pipeline
    from app.routers.behavior import TYPE_BEHAVIOR_MAP

    if not hubspot_scan.is_configured():
        raise HTTPException(status_code=400, detail="HUBSPOT_API_KEY not set")

    query = (req.query or "").strip()
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    # Search HubSpot
    result = hubspot_scan.search_companies(query, limit=100)
    if not result.get("available"):
        raise HTTPException(status_code=502, detail="HubSpot search unavailable")

    # Fuzzy-name normalizer
    def normalize(s: str) -> str:
        s = (s or "").lower().strip()
        for suffix in [" insurance", " insurance company", " agency", " group",
                       " inc", " inc.", " llc", " co.", " company", " corp",
                       " corporation"]:
            if s.endswith(suffix):
                s = s[: -len(suffix)].strip()
        return s

    existing = set()
    for p in db.query(Prospect).all():
        existing.add(normalize(p.name))
    for c in db.query(Client).all():
        existing.add(normalize(c.name))

    all_clients = db.query(Client).all()
    active_clients = [c for c in all_clients if c.active]

    added = []
    skipped = []
    relationships_added = 0

    for company in result.get("results", []):
        name = (company.get("name") or "").strip()
        if not name:
            # HubSpot has many records with just a domain and no name
            continue

        norm = normalize(name)
        if norm in existing:
            skipped.append(name)
            continue

        inferred_type = type_inference.infer_type(
            name=name,
            description=company.get("description") or "",
            domain=company.get("domain") or "",
            employees=company.get("employees"),
        )

        p = Prospect(
            name=name,
            domain=company.get("domain"),
            website=company.get("domain"),
            description=company.get("description") or company.get("industry", ""),
            hq_city=company.get("city"),
            hq_state=company.get("state"),
            employees=company.get("employees"),
            type=inferred_type,
        )
        db.add(p)
        db.flush()

        try:
            profile_generator.upsert_profile(p, db, run_enrichment=False)
        except Exception:
            pass

        if inferred_type in TYPE_BEHAVIOR_MAP:
            db.add(BehaviorProfile(
                prospect_id=p.id,
                assessed_by="hubspot_import",
                assessed_at=datetime.utcnow(),
                partnership_history=f"Imported from HubSpot. Inferred type: {inferred_type}.",
                **TYPE_BEHAVIOR_MAP[inferred_type],
            ))

        hs_id = company.get("hubspot_id")
        if hs_id:
            try:
                for contact in hubspot_scan.get_company_contacts(hs_id):
                    cname = (contact.get("name") or "").strip()
                    if not cname:
                        continue
                    db.add(Relationship(
                        prospect_id=p.id,
                        contact_name=cname,
                        contact_title=contact.get("title", ""),
                        contact_email=contact.get("email", ""),
                        score=2,
                        source="HubSpot",
                        context="Imported from HubSpot CRM.",
                        warmest_path="HubSpot CRM",
                    ))
                    relationships_added += 1
            except Exception:
                pass

        # Add to EVERY client's pipeline (not just active) so Layer 1 and pipelines stay in sync
        for cl in all_clients:
            if cl.name.lower() == p.name.lower():
                continue
            db.add(PipelineEntry(
                client_id=cl.id,
                prospect_id=p.id,
                source=f"HubSpot ad-hoc import: {query}",
            ))

        added.append({"name": name, "type": inferred_type})
        existing.add(norm)

    db.commit()

    # Rescore active pipelines so new entries get scored immediately
    scored_counts = {}
    for cl in active_clients:
        scored_counts[cl.name] = _auto_score_pipeline(cl.id, db)
    db.commit()

    return {
        "status": "ok",
        "query": query,
        "hubspot_matched": len(result.get("results", [])),
        "imported": len(added),
        "imported_detail": added,
        "skipped": len(skipped),
        "skipped_names": skipped,
        "relationships_added": relationships_added,
        "scored": scored_counts,
    }
