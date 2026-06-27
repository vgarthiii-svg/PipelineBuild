"""
Lightweight scheduler for the BD Pipeline Agent.

- Jobs are declared in `JOB_REGISTRY` at the bottom of this file.
- A background asyncio loop wakes every minute, checks which jobs are due,
  and runs them. Last-run metadata is persisted in the `scheduled_jobs` table.
- Schedules supported: `daily@HH:MM`, `weekly@<day>@HH:MM`, `hourly`, `interval@<minutes>m`.

Adding a new job:
1. Write a function that takes a SQLAlchemy Session and returns a dict result.
2. Register it in JOB_REGISTRY with a unique `job_key`, human name, schedule.
3. Restart the server; scheduler will seed the row on startup if missing.
"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Callable, Dict, List, Optional

from app.database import SessionLocal
from app.models import ScheduledJob

log = logging.getLogger(__name__)

_DAY_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


# ================================================================
#  Schedule parsing + next-run calculation
# ================================================================

def _next_run(schedule: str, now: Optional[datetime] = None) -> datetime:
    """
    Given a schedule string, return the next datetime (>= now) at which this job fires.
    """
    now = now or datetime.now()
    schedule = schedule.strip().lower()

    if schedule == "hourly":
        nxt = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        return nxt

    if schedule.startswith("interval@") and schedule.endswith("m"):
        minutes = int(schedule.split("@")[1][:-1])
        return now + timedelta(minutes=minutes)

    if schedule.startswith("daily@"):
        hh, mm = schedule.split("@")[1].split(":")
        target = time(int(hh), int(mm))
        nxt = datetime.combine(now.date(), target)
        if nxt <= now:
            nxt += timedelta(days=1)
        return nxt

    if schedule.startswith("weekly@"):
        parts = schedule.split("@")
        day_str = parts[1]
        hh, mm = parts[2].split(":")
        target_time = time(int(hh), int(mm))
        target_dow = _DAY_INDEX.get(day_str[:3], 0)
        days_ahead = (target_dow - now.weekday()) % 7
        candidate = datetime.combine(now.date(), target_time) + timedelta(days=days_ahead)
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate

    # Unknown schedule — skip forward a day so we don't hot-loop
    log.warning("Unknown schedule format: %s. Defaulting to 24h from now.", schedule)
    return now + timedelta(days=1)


# ================================================================
#  Built-in jobs
# ================================================================

def _job_nightly_rescore(db) -> dict:
    """
    Rescore every active client's pipeline. No API cost.
    Good hygiene job — keeps scores in sync with behavior/intent/profile updates.
    """
    from app.models import Client
    from app.routers.clients import _auto_score_pipeline

    active_clients = db.query(Client).filter(Client.active == True).all()
    results = []
    for c in active_clients:
        try:
            count = _auto_score_pipeline(c.id, db)
            results.append(f"{c.name}: {count} rows")
        except Exception as e:
            log.exception("Rescore failed for %s", c.name)
            results.append(f"{c.name}: error - {e}")
    db.commit()
    return {
        "active_clients": len(active_clients),
        "summary": results,
        "ran_at": datetime.utcnow().isoformat() + "Z",
    }


def _job_weekly_behavior_refresh(db) -> dict:
    """
    Re-infer behavior profiles for prospects whose type has been set but whose
    behavior profile is missing or older than 30 days. Free, heuristic only.
    """
    from app.models import Prospect, BehaviorProfile
    from app.routers.behavior import TYPE_BEHAVIOR_MAP

    stale_cutoff = datetime.utcnow() - timedelta(days=30)
    prospects = db.query(Prospect).filter(Prospect.type != None).all()

    refreshed = 0
    created = 0
    for p in prospects:
        if p.type not in TYPE_BEHAVIOR_MAP:
            continue
        bp = db.query(BehaviorProfile).filter(BehaviorProfile.prospect_id == p.id).first()
        defaults = TYPE_BEHAVIOR_MAP[p.type]
        if not bp:
            bp = BehaviorProfile(
                prospect_id=p.id,
                assessed_by="scheduler_auto",
                assessed_at=datetime.utcnow(),
                partnership_history=f"Auto-inferred from type: {p.type}",
                **defaults,
            )
            db.add(bp)
            created += 1
        elif bp.assessed_at and bp.assessed_at < stale_cutoff and bp.assessed_by in ("scheduler_auto", "heuristic_auto"):
            # Only refresh auto-inferred rows; don't trample user-edited ones
            for k, v in defaults.items():
                setattr(bp, k, v)
            bp.assessed_at = datetime.utcnow()
            refreshed += 1
    db.commit()
    return {"created": created, "refreshed": refreshed, "total_prospects": len(prospects)}


def _job_nightly_hubspot_sync(db) -> dict:
    """
    Pull companies from the configured HubSpot BD list (HUBSPOT_BD_LIST_ID env var).
    For each:
      - Upsert into prospects table (add if new, update metadata if existing)
      - Pull their contacts into the relationships table
      - If new, auto-add into every active client's pipeline
    Does NOT delete prospects that disappear from the list (conservative).
    """
    import os
    from app.models import Prospect, Relationship, Client, PipelineEntry
    from app.services import hubspot_scan, type_inference

    if not hubspot_scan.is_configured():
        return {"status": "skipped", "reason": "HUBSPOT_API_KEY not set"}

    list_id = os.environ.get("HUBSPOT_BD_LIST_ID", "").strip()
    if not list_id:
        return {
            "status": "skipped",
            "reason": "HUBSPOT_BD_LIST_ID not set in .env. See agent description for setup instructions.",
        }

    recent = hubspot_scan.list_companies_in_list(list_id, limit=500)
    if not recent.get("available"):
        return {"status": "error", "error": recent.get("error", "HubSpot unavailable")}

    added_prospects = []
    updated_prospects = []
    added_relationships = 0

    # Sync to ALL clients so Layer 1 and pipelines stay consistent
    all_clients = db.query(Client).all()

    for company in recent.get("results", []):
        name = (company.get("name") or "").strip()
        if not name:
            continue

        existing = db.query(Prospect).filter(Prospect.name.ilike(name)).first()
        if existing:
            # Update metadata if richer info came through
            changed = False
            if not existing.domain and company.get("domain"):
                existing.domain = company["domain"]; changed = True
            if not existing.description and company.get("description"):
                existing.description = company["description"]; changed = True
            if not existing.hq_city and company.get("city"):
                existing.hq_city = company["city"]; changed = True
            if not existing.hq_state and company.get("state"):
                existing.hq_state = company["state"]; changed = True
            if not existing.employees and company.get("employees"):
                existing.employees = company["employees"]; changed = True
            if changed:
                updated_prospects.append(name)
            prospect = existing
            is_new = False
        else:
            inferred_type = type_inference.infer_type(
                name=name,
                description=company.get("description") or "",
                domain=company.get("domain") or "",
                employees=company.get("employees"),
            )
            prospect = Prospect(
                name=name,
                domain=company.get("domain"),
                website=company.get("domain"),
                description=company.get("description"),
                hq_city=company.get("city"),
                hq_state=company.get("state"),
                employees=company.get("employees"),
                type=inferred_type,
            )
            db.add(prospect)
            db.flush()
            added_prospects.append(name)
            is_new = True

        # Pull contacts into relationships table
        hs_id = company.get("hubspot_id")
        if hs_id:
            try:
                contacts = hubspot_scan.get_company_contacts(hs_id)
                for c in contacts:
                    cname = (c.get("name") or "").strip()
                    if not cname:
                        continue
                    existing_rel = (
                        db.query(Relationship)
                        .filter(Relationship.prospect_id == prospect.id,
                                Relationship.contact_name.ilike(cname))
                        .first()
                    )
                    if existing_rel:
                        # Update title/email if better info arrived
                        if c.get("title") and not existing_rel.contact_title:
                            existing_rel.contact_title = c["title"]
                        if c.get("email") and not existing_rel.contact_email:
                            existing_rel.contact_email = c["email"]
                    else:
                        db.add(Relationship(
                            prospect_id=prospect.id,
                            contact_name=cname,
                            contact_title=c.get("title", ""),
                            contact_email=c.get("email", ""),
                            score=2,  # HubSpot presence = RS 2 (Light)
                            source="HubSpot",
                            context="Imported from HubSpot CRM.",
                            warmest_path="HubSpot CRM",
                        ))
                        added_relationships += 1
            except Exception as e:
                log.exception("Failed to pull HubSpot contacts for %s", name)

        # For NEW prospects: add to EVERY client's pipeline (active + inactive)
        if is_new:
            for client in all_clients:
                if client.name.lower() == prospect.name.lower():
                    continue
                already = db.query(PipelineEntry).filter(
                    PipelineEntry.client_id == client.id,
                    PipelineEntry.prospect_id == prospect.id,
                ).first()
                if not already:
                    db.add(PipelineEntry(
                        client_id=client.id,
                        prospect_id=prospect.id,
                        source="Nightly HubSpot sync",
                    ))

    db.commit()

    return {
        "status": "ok",
        "total_from_hubspot": len(recent.get("results", [])),
        "new_prospects": len(added_prospects),
        "updated_prospects": len(updated_prospects),
        "new_relationships": added_relationships,
        "added_prospect_names": added_prospects[:20],
        "updated_prospect_names": updated_prospects[:20],
        "ran_at": datetime.utcnow().isoformat() + "Z",
    }


def _job_daily_pipeline_snapshot(db) -> dict:
    """
    Capture a daily snapshot of pipeline metrics per active client.
    Logged (not returned fully) so the Analytics view can show historical trends later.
    """
    from app.models import Client, PipelineEntry
    active = db.query(Client).filter(Client.active == True).all()
    snapshots = []
    for c in active:
        entries = db.query(PipelineEntry).filter(PipelineEntry.client_id == c.id).all()
        by_tier = {"hot": 0, "warm": 0, "monitor": 0, "pass": 0, "filtered": 0, "unscored": 0}
        for e in entries:
            key = e.tier or "unscored"
            by_tier[key] = by_tier.get(key, 0) + 1
        avg_ms = 0.0
        scored = [e.matchmaker_score for e in entries if e.matchmaker_score is not None]
        if scored:
            avg_ms = round(sum(scored) / len(scored), 1)
        snapshots.append({
            "client": c.name,
            "total": len(entries),
            "avg_matchmaker": avg_ms,
            **by_tier,
        })
    return {"snapshots": snapshots, "date": datetime.utcnow().date().isoformat()}


# ================================================================
#  Job registry
# ================================================================

JOB_REGISTRY: Dict[str, dict] = {
    "nightly_rescore": {
        "name": "Nightly pipeline rescore",
        "description": "Recalculate Matchmaker scores for every active client's pipeline. Free. Keeps scores in sync with data changes.",
        "schedule": "daily@03:00",
        "function": _job_nightly_rescore,
    },
    "nightly_hubspot_sync": {
        "name": "Nightly HubSpot sync",
        "description": "Pull companies from the HubSpot list you configure as your BD pipeline (via HUBSPOT_BD_LIST_ID in .env). Adds new ones as prospects, pulls their contacts into relationships, auto-adds new prospects to every active client's pipeline. Skips run if no list ID is configured. Runs at 05:00 after the 03:00 rescore + 04:00 behavior refresh.",
        "schedule": "daily@05:00",
        "function": _job_nightly_hubspot_sync,
    },
    "weekly_behavior_refresh": {
        "name": "Weekly behavior profile refresh",
        "description": "Re-infer stale behavior profiles from company type. Only touches auto-inferred rows, never user-edited ones.",
        "schedule": "weekly@mon@04:00",
        "function": _job_weekly_behavior_refresh,
    },
    "daily_pipeline_snapshot": {
        "name": "Daily pipeline snapshot",
        "description": "Capture daily pipeline health metrics per active client. Feeds future analytics view.",
        "schedule": "daily@02:00",
        "function": _job_daily_pipeline_snapshot,
    },
}


# ================================================================
#  Scheduler engine
# ================================================================

def seed_jobs():
    """Ensure every JOB_REGISTRY entry has a row in scheduled_jobs. Idempotent."""
    db = SessionLocal()
    try:
        for key, spec in JOB_REGISTRY.items():
            existing = db.query(ScheduledJob).filter(ScheduledJob.job_key == key).first()
            if not existing:
                db.add(ScheduledJob(
                    job_key=key,
                    name=spec["name"],
                    description=spec["description"],
                    schedule=spec["schedule"],
                    enabled=True,
                    next_run=_next_run(spec["schedule"]),
                ))
                log.info("Seeded new scheduled job: %s", key)
            else:
                # Keep name/description/schedule in sync with registry
                existing.name = spec["name"]
                existing.description = spec["description"]
                existing.schedule = spec["schedule"]
                if not existing.next_run:
                    existing.next_run = _next_run(spec["schedule"])
        db.commit()
    finally:
        db.close()


def run_job(job_key: str) -> dict:
    """Run a job by key, synchronously. Updates scheduled_jobs row with result."""
    spec = JOB_REGISTRY.get(job_key)
    if not spec:
        raise KeyError(f"No job registered with key: {job_key}")

    db = SessionLocal()
    try:
        row = db.query(ScheduledJob).filter(ScheduledJob.job_key == job_key).first()
        if not row:
            raise KeyError(f"Job {job_key} not seeded in DB")

        row.last_status = "running"
        row.last_run = datetime.utcnow()
        db.commit()

        try:
            result = spec["function"](db)
            import json as _json
            row.last_status = "ok"
            row.last_output = _json.dumps(result, default=str)[:4000]
            row.next_run = _next_run(row.schedule)
            db.commit()
            log.info("Job %s completed: %s", job_key, result)
            return {"status": "ok", "result": result}
        except Exception as e:
            log.exception("Job %s failed", job_key)
            row.last_status = "error"
            row.last_output = str(e)[:4000]
            row.next_run = _next_run(row.schedule)
            db.commit()
            return {"status": "error", "error": str(e)}
    finally:
        db.close()


async def _scheduler_loop(tick_seconds: int = 60):
    """Background loop that checks for due jobs every tick_seconds."""
    # Wait 2 minutes before first tick so startup isn't slammed
    await asyncio.sleep(120)
    while True:
        try:
            now = datetime.now()
            db = SessionLocal()
            try:
                due_jobs = (
                    db.query(ScheduledJob)
                    .filter(ScheduledJob.enabled == True)
                    .filter(ScheduledJob.next_run != None)
                    .filter(ScheduledJob.next_run <= now)
                    .all()
                )
                due_keys = [j.job_key for j in due_jobs]
            finally:
                db.close()

            for key in due_keys:
                log.info("Firing scheduled job: %s", key)
                try:
                    run_job(key)
                except Exception:
                    log.exception("Failed to run job %s from scheduler", key)
        except Exception:
            log.exception("Scheduler tick failed")

        await asyncio.sleep(tick_seconds)


def start_scheduler():
    """Kick off the background scheduler loop. Call once from FastAPI startup."""
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_scheduler_loop())
        log.info("Agent scheduler started. %d jobs registered.", len(JOB_REGISTRY))
    except Exception:
        log.exception("Failed to start agent scheduler")
