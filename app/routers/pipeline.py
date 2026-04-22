import csv
import io
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.database import get_db
from app.models import (
    PipelineEntry, Prospect, Client, ScoringCriterion,
    CriterionScore, Relationship, ActivityLog,
    BehaviorProfile, IntentSignal, IdentityFilter,
)
from app.schemas import (
    PipelineEntryCreate, PipelineEntryOut, PipelineWeightUpdate,
    PipelineBulkCreate, PipelineSummary, CriterionScoreCreate, CriterionScoreOut,
)
from app.scoring import (
    calculate_pmf, calculate_matchmaker, assign_tier,
    run_identity_filter, calculate_friction_coefficient, calculate_intent_multiplier,
    heuristic_score_prospect,
)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


def _enrich_entry(entry: PipelineEntry, db: Session) -> dict:
    """Add prospect info and best contact to a pipeline entry."""
    prospect = entry.prospect
    # Find best relationship
    best_rel = (
        db.query(Relationship)
        .filter(Relationship.prospect_id == entry.prospect_id)
        .order_by(Relationship.score.desc())
        .first()
    )
    return {
        "id": entry.id,
        "client_id": entry.client_id,
        "prospect_id": entry.prospect_id,
        "source": entry.source,
        "tier": entry.tier,
        "pmf_score": entry.pmf_score,
        "relationship_score": entry.relationship_score,
        "matchmaker_score": entry.matchmaker_score,
        "pmf_weight": entry.pmf_weight,
        "rs_weight": entry.rs_weight,
        "status": entry.status,
        "next_action": entry.next_action,
        "notes": entry.notes,
        "prospect_name": prospect.name if prospect else None,
        "prospect_type": prospect.type if prospect else None,
        "best_contact": best_rel.contact_name if best_rel else None,
        "warmest_path": best_rel.warmest_path if best_rel else None,
        "filtered": entry.filtered if hasattr(entry, 'filtered') and entry.filtered else False,
        "filter_reason": entry.filter_reason if hasattr(entry, 'filter_reason') else None,
        "friction_coefficient": entry.friction_coefficient if hasattr(entry, 'friction_coefficient') and entry.friction_coefficient else 1.0,
        "intent_multiplier": entry.intent_multiplier if hasattr(entry, 'intent_multiplier') and entry.intent_multiplier else 1.0,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


@router.get("/{client_id}", response_model=List[PipelineEntryOut])
def get_pipeline(
    client_id: int,
    tier: Optional[str] = None,
    status: Optional[str] = None,
    min_rs: Optional[int] = None,
    max_rs: Optional[int] = None,
    min_pmf: Optional[float] = None,
    sort_by: str = Query("matchmaker_score", regex="^(matchmaker_score|pmf_score|relationship_score|name)$"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = (
        db.query(PipelineEntry)
        .options(joinedload(PipelineEntry.prospect))
        .filter(PipelineEntry.client_id == client_id)
    )

    if tier:
        q = q.filter(PipelineEntry.tier == tier)
    if status:
        q = q.filter(PipelineEntry.status == status)
    if min_rs is not None:
        q = q.filter(PipelineEntry.relationship_score >= min_rs)
    if max_rs is not None:
        q = q.filter(PipelineEntry.relationship_score <= max_rs)
    if min_pmf is not None:
        q = q.filter(PipelineEntry.pmf_score >= min_pmf)

    if sort_by == "name":
        q = q.join(Prospect).order_by(
            Prospect.name.asc() if sort_dir == "asc" else Prospect.name.desc()
        )
    else:
        col = getattr(PipelineEntry, sort_by)
        # Put nulls last
        if sort_dir == "desc":
            q = q.order_by(col.desc().nullslast())
        else:
            q = q.order_by(col.asc().nullslast())

    entries = q.all()
    return [_enrich_entry(e, db) for e in entries]


@router.post("/", response_model=PipelineEntryOut)
def create_pipeline_entry(data: PipelineEntryCreate, db: Session = Depends(get_db)):
    # Check for existing
    existing = (
        db.query(PipelineEntry)
        .filter(
            PipelineEntry.client_id == data.client_id,
            PipelineEntry.prospect_id == data.prospect_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Entry already exists for this client/prospect")

    entry = PipelineEntry(**data.dict())
    # Carry over relationship score from relationships table
    best_rel = (
        db.query(Relationship)
        .filter(Relationship.prospect_id == data.prospect_id)
        .order_by(Relationship.score.desc())
        .first()
    )
    if best_rel:
        entry.relationship_score = best_rel.score

    db.add(entry)
    db.commit()
    db.refresh(entry)

    # Log activity
    log = ActivityLog(
        pipeline_entry_id=entry.id,
        action="added_to_pipeline",
        new_value=f"Added to pipeline for client {data.client_id}",
        notes=data.source,
    )
    db.add(log)
    db.commit()

    return _enrich_entry(entry, db)


@router.post("/bulk", response_model=List[PipelineEntryOut])
def bulk_create_pipeline(data: PipelineBulkCreate, db: Session = Depends(get_db)):
    entries = []
    for pid in data.prospect_ids:
        existing = (
            db.query(PipelineEntry)
            .filter(PipelineEntry.client_id == data.client_id, PipelineEntry.prospect_id == pid)
            .first()
        )
        if existing:
            entries.append(existing)
            continue

        entry = PipelineEntry(
            client_id=data.client_id,
            prospect_id=pid,
            source=data.source,
            source_date=data.source_date,
        )
        best_rel = (
            db.query(Relationship)
            .filter(Relationship.prospect_id == pid)
            .order_by(Relationship.score.desc())
            .first()
        )
        if best_rel:
            entry.relationship_score = best_rel.score
        db.add(entry)
        db.flush()
        entries.append(entry)

    db.commit()
    return [_enrich_entry(e, db) for e in entries]


@router.delete("/{entry_id}")
def delete_pipeline_entry(entry_id: int, db: Session = Depends(get_db)):
    """Remove a company from the pipeline."""
    entry = db.query(PipelineEntry).filter(PipelineEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Pipeline entry not found")

    prospect_name = entry.prospect.name if entry.prospect else "Unknown"

    # Delete related criterion scores
    db.query(CriterionScore).filter(CriterionScore.pipeline_entry_id == entry_id).delete()
    # Delete related intro packages
    from app.models import IntroPackage
    db.query(IntroPackage).filter(IntroPackage.pipeline_entry_id == entry_id).delete()
    # Delete related activity logs
    db.query(ActivityLog).filter(ActivityLog.pipeline_entry_id == entry_id).delete()

    db.delete(entry)

    # Log the removal (standalone, no entry reference)
    log = ActivityLog(
        action="removed_from_pipeline",
        new_value=f"{prospect_name} removed from pipeline",
    )
    db.add(log)

    db.commit()
    return {"status": "removed", "prospect_name": prospect_name}


@router.delete("/bulk/{client_id}")
def bulk_delete_pipeline(client_id: int, entry_ids: List[int], db: Session = Depends(get_db)):
    """Remove multiple companies from the pipeline."""
    removed = []
    for eid in entry_ids:
        entry = db.query(PipelineEntry).filter(
            PipelineEntry.id == eid, PipelineEntry.client_id == client_id
        ).first()
        if entry:
            name = entry.prospect.name if entry.prospect else "Unknown"
            db.query(CriterionScore).filter(CriterionScore.pipeline_entry_id == eid).delete()
            from app.models import IntroPackage
            db.query(IntroPackage).filter(IntroPackage.pipeline_entry_id == eid).delete()
            db.query(ActivityLog).filter(ActivityLog.pipeline_entry_id == eid).delete()
            db.delete(entry)
            removed.append(name)

    if removed:
        log = ActivityLog(
            action="bulk_removed",
            new_value=f"Removed {len(removed)} companies: {', '.join(removed)}",
        )
        db.add(log)

    db.commit()
    return {"status": "removed", "count": len(removed), "companies": removed}


@router.post("/quick-add")
def quick_add(client_id: int, company_name: str, db: Session = Depends(get_db)):
    """
    Add a single company by name to the current client's pipeline AND to every other client's pipeline.
    This way the company is scored against every client automatically.
    """
    company_name = company_name.strip()
    if not company_name:
        raise HTTPException(status_code=400, detail="Company name required")

    # Find or create prospect
    prospect = db.query(Prospect).filter(Prospect.name.ilike(company_name)).first()
    if not prospect:
        from app.services import profile_generator, type_inference
        # Infer accurate type (uses HubSpot + Apollo + keyword matching, all free)
        inferred_type = type_inference.infer_type(name=company_name)
        prospect = Prospect(name=company_name, type=inferred_type)
        db.add(prospect)
        db.flush()
        # Auto-generate business profile (free Layer 1 + Layer 2 if keys set)
        try:
            profile_generator.upsert_profile(prospect, db, run_enrichment=True)
        except Exception as e:
            print(f"[PIPELINE] Profile generation failed: {e}")

    # Add to EVERY client's pipeline (not just the current one)
    all_clients = db.query(Client).all()
    best_rel = (
        db.query(Relationship)
        .filter(Relationship.prospect_id == prospect.id)
        .order_by(Relationship.score.desc())
        .first()
    )

    current_entry = None
    for cl in all_clients:
        # Don't add a client as a prospect in its own pipeline
        if cl.name.lower() == prospect.name.lower():
            continue

        existing = db.query(PipelineEntry).filter(
            PipelineEntry.client_id == cl.id,
            PipelineEntry.prospect_id == prospect.id,
        ).first()
        if existing:
            if cl.id == client_id:
                current_entry = existing
            continue

        entry = PipelineEntry(
            client_id=cl.id,
            prospect_id=prospect.id,
            source="Quick add (auto-added to all clients)",
        )
        if best_rel:
            entry.relationship_score = best_rel.score

        db.add(entry)
        db.flush()

        if cl.id == client_id:
            current_entry = entry

    # Re-score all client pipelines that got the new prospect (heuristic, free)
    from app.routers.clients import _auto_score_pipeline
    for cl in all_clients:
        if cl.name.lower() != prospect.name.lower():
            _auto_score_pipeline(cl.id, db)

    if not current_entry:
        raise HTTPException(status_code=500, detail="Could not add to current client's pipeline")

    log = ActivityLog(
        pipeline_entry_id=current_entry.id,
        action="added_to_pipeline",
        new_value=f"{company_name} added to all {len(all_clients)} client pipelines",
        notes="Quick add (universal)",
    )
    db.add(log)
    db.commit()
    db.refresh(current_entry)
    return _enrich_entry(current_entry, db)


@router.post("/{entry_id}/score")
def score_entry(entry_id: int, scores: List[CriterionScoreCreate], db: Session = Depends(get_db)):
    """Score a single pipeline entry with criterion scores."""
    entry = db.query(PipelineEntry).filter(PipelineEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Pipeline entry not found")

    old_tier = entry.tier
    old_matchmaker = entry.matchmaker_score

    # Upsert criterion scores
    for s in scores:
        existing = (
            db.query(CriterionScore)
            .filter(
                CriterionScore.pipeline_entry_id == entry_id,
                CriterionScore.criterion_id == s.criterion_id,
            )
            .first()
        )
        if existing:
            existing.score = s.score
            existing.reasoning = s.reasoning
        else:
            cs = CriterionScore(
                pipeline_entry_id=entry_id,
                criterion_id=s.criterion_id,
                score=s.score,
                reasoning=s.reasoning,
            )
            db.add(cs)

    db.flush()

    # Recalculate PMF
    criterion_scores = (
        db.query(CriterionScore)
        .filter(CriterionScore.pipeline_entry_id == entry_id)
        .all()
    )
    scores_and_weights = []
    for cs in criterion_scores:
        criterion = db.query(ScoringCriterion).filter(ScoringCriterion.id == cs.criterion_id).first()
        if criterion:
            scores_and_weights.append((cs.score, criterion.weight))

    pmf = calculate_pmf(scores_and_weights)
    matchmaker = calculate_matchmaker(pmf, entry.relationship_score, entry.pmf_weight, entry.rs_weight)
    tier = assign_tier(matchmaker)

    entry.pmf_score = round(pmf, 1)
    entry.matchmaker_score = round(matchmaker, 1)
    entry.tier = tier
    entry.status = "scored" if entry.status == "new" else entry.status
    entry.updated_at = datetime.utcnow()

    # Log if tier changed
    if old_tier != tier:
        log = ActivityLog(
            pipeline_entry_id=entry_id,
            action="tier_changed",
            old_value=old_tier,
            new_value=tier,
            notes=f"Matchmaker: {old_matchmaker} -> {round(matchmaker, 1)}",
        )
        db.add(log)

    log = ActivityLog(
        pipeline_entry_id=entry_id,
        action="scored",
        new_value=f"PMF: {round(pmf, 1)}, MS: {round(matchmaker, 1)}, Tier: {tier}",
    )
    db.add(log)

    db.commit()
    db.refresh(entry)
    return _enrich_entry(entry, db)


@router.post("/{client_id}/score-all")
def score_all(client_id: int, db: Session = Depends(get_db)):
    """Recalculate Matchmaker Score for all entries using 4-layer formula."""
    entries = db.query(PipelineEntry).filter(PipelineEntry.client_id == client_id).all()
    results = []

    # Load client's identity filter and behavior profile
    client_filter = db.query(IdentityFilter).filter(IdentityFilter.client_id == client_id).first()

    # Get client behavior profile (look up the client as a prospect if it exists)
    client = db.query(Client).filter(Client.id == client_id).first()
    client_prospect = db.query(Prospect).filter(Prospect.name.ilike(client.name)).first() if client else None
    client_behavior = None
    if client_prospect:
        client_behavior = db.query(BehaviorProfile).filter(BehaviorProfile.prospect_id == client_prospect.id).first()

    # Load the currently-active criteria ONCE (fresh for this rescore)
    active_criteria = db.query(ScoringCriterion).filter(
        ScoringCriterion.client_id == client_id,
        ScoringCriterion.active == True,
    ).all()
    active_criterion_ids = {c.id for c in active_criteria}

    for entry in entries:
        prospect = db.query(Prospect).filter(Prospect.id == entry.prospect_id).first()

        # Layer 1: Identity Filter
        passed, reason = run_identity_filter(prospect, client_filter)
        if not passed:
            entry.filtered = True
            entry.filter_reason = reason
            entry.tier = "filtered"
            entry.updated_at = datetime.utcnow()
            results.append(_enrich_entry(entry, db))
            continue
        else:
            entry.filtered = False
            entry.filter_reason = None

        # Layer 2: PMF — ALWAYS regenerate criterion scores from the current active set
        # so newly-toggled criteria immediately affect scores and toggled-off criteria stop affecting them.
        db.query(CriterionScore).filter(CriterionScore.pipeline_entry_id == entry.id).delete(synchronize_session=False)

        criterion_scores = []
        if prospect and active_criteria:
            heuristic_results = heuristic_score_prospect(prospect, client, active_criteria)
            for h in heuristic_results:
                cs = CriterionScore(
                    pipeline_entry_id=entry.id,
                    criterion_id=h["criterion_id"],
                    score=h["score"],
                    reasoning=h["reasoning"],
                )
                db.add(cs)
                criterion_scores.append(type('CS', (), {"score": h["score"], "criterion_id": h["criterion_id"]}))

        scores_and_weights = []
        for cs in criterion_scores:
            cid = cs.criterion_id if hasattr(cs, 'criterion_id') else None
            criterion = db.query(ScoringCriterion).filter(ScoringCriterion.id == cid).first() if cid else None
            if criterion:
                scores_and_weights.append((cs.score, criterion.weight))

        if scores_and_weights:
            pmf = calculate_pmf(scores_and_weights)
        elif entry.pmf_score is not None:
            pmf = entry.pmf_score
        else:
            pmf = 0.0

        # Layer 3: Friction from behavior comparison
        prospect_behavior = db.query(BehaviorProfile).filter(BehaviorProfile.prospect_id == entry.prospect_id).first()
        friction = calculate_friction_coefficient(client_behavior, prospect_behavior)
        entry.friction_coefficient = friction

        # Layer 4: Intent from signals
        intent_signals = db.query(IntentSignal).filter(IntentSignal.prospect_id == entry.prospect_id).all()
        intent = calculate_intent_multiplier(intent_signals)
        entry.intent_multiplier = intent

        # Calculate Matchmaker with all 4 layers
        matchmaker = calculate_matchmaker(pmf, entry.relationship_score, friction, intent)
        tier = assign_tier(matchmaker)

        entry.pmf_score = round(pmf, 1)
        entry.matchmaker_score = round(matchmaker, 1)
        entry.tier = tier
        entry.updated_at = datetime.utcnow()
        results.append(_enrich_entry(entry, db))

    db.commit()
    return results


@router.put("/{entry_id}")
def update_entry(entry_id: int, status: Optional[str] = None, next_action: Optional[str] = None, notes: Optional[str] = None, db: Session = Depends(get_db)):
    entry = db.query(PipelineEntry).filter(PipelineEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Pipeline entry not found")

    if status:
        old_status = entry.status
        entry.status = status
        log = ActivityLog(
            pipeline_entry_id=entry_id,
            action="status_changed",
            old_value=old_status,
            new_value=status,
        )
        db.add(log)
    if next_action is not None:
        entry.next_action = next_action
    if notes is not None:
        entry.notes = notes

    entry.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(entry)
    return _enrich_entry(entry, db)


@router.put("/{client_id}/weights")
def update_weights(client_id: int, data: PipelineWeightUpdate, db: Session = Depends(get_db)):
    """Update PMF/RS weights for all entries in a client pipeline and rescore."""
    entries = db.query(PipelineEntry).filter(PipelineEntry.client_id == client_id).all()

    for entry in entries:
        entry.pmf_weight = data.pmf_weight
        entry.rs_weight = data.rs_weight

        pmf = entry.pmf_score or 0.0
        matchmaker = calculate_matchmaker(pmf, entry.relationship_score, data.pmf_weight, data.rs_weight)
        entry.matchmaker_score = round(matchmaker, 1)
        entry.tier = assign_tier(matchmaker)
        entry.updated_at = datetime.utcnow()

    db.commit()
    return [_enrich_entry(e, db) for e in entries]


@router.get("/{client_id}/summary", response_model=PipelineSummary)
def get_summary(client_id: int, db: Session = Depends(get_db)):
    entries = db.query(PipelineEntry).filter(PipelineEntry.client_id == client_id).all()
    total = len(entries)
    hot = sum(1 for e in entries if e.tier == "hot")
    warm = sum(1 for e in entries if e.tier == "warm")
    monitor = sum(1 for e in entries if e.tier == "monitor")
    pass_count = sum(1 for e in entries if e.tier == "pass")
    unscored = sum(1 for e in entries if e.tier == "unscored")
    filtered_count = sum(1 for e in entries if e.tier == "filtered")

    scored = [e for e in entries if e.matchmaker_score is not None and e.tier != "filtered"]
    avg_matchmaker = round(sum(e.matchmaker_score for e in scored) / len(scored), 1) if scored else None
    avg_pmf = round(sum(e.pmf_score for e in scored if e.pmf_score) / max(len([e for e in scored if e.pmf_score]), 1), 1) if scored else None
    avg_rs = round(sum(e.relationship_score for e in entries) / total, 1) if total else None

    return PipelineSummary(
        total=total, hot=hot, warm=warm, monitor=monitor,
        pass_count=pass_count, unscored=unscored, filtered=filtered_count,
        avg_matchmaker=avg_matchmaker, avg_pmf=avg_pmf, avg_rs=avg_rs,
    )


@router.get("/{client_id}/export")
def export_csv(client_id: int, db: Session = Depends(get_db)):
    """Export pipeline as CSV."""
    entries = (
        db.query(PipelineEntry)
        .options(joinedload(PipelineEntry.prospect))
        .filter(PipelineEntry.client_id == client_id)
        .order_by(PipelineEntry.matchmaker_score.desc().nullslast())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Rank", "Company", "Type", "PMF Score", "RS Score",
        "Matchmaker Score", "Tier", "Status", "Best Contact", "Next Action",
    ])

    for i, entry in enumerate(entries, 1):
        best_rel = (
            db.query(Relationship)
            .filter(Relationship.prospect_id == entry.prospect_id)
            .order_by(Relationship.score.desc())
            .first()
        )
        writer.writerow([
            i,
            entry.prospect.name if entry.prospect else "",
            entry.prospect.type if entry.prospect else "",
            entry.pmf_score or "",
            entry.relationship_score,
            entry.matchmaker_score or "",
            entry.tier,
            entry.status,
            best_rel.contact_name if best_rel else "",
            entry.next_action or "",
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=pipeline_export_{client_id}.csv"},
    )


@router.get("/{entry_id}/breakdown")
def get_score_breakdown(entry_id: int, db: Session = Depends(get_db)):
    """
    Full traceability: explain exactly how an entry's Matchmaker Score was computed.
    Returns per-criterion contributions to PMF, the PMF/RS blend, and the friction/intent multipliers.
    """
    entry = db.query(PipelineEntry).filter(PipelineEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Pipeline entry not found")

    # Per-criterion scores (what went into PMF)
    scores = db.query(CriterionScore).filter(CriterionScore.pipeline_entry_id == entry_id).all()
    criteria = {c.id: c for c in db.query(ScoringCriterion).filter(ScoringCriterion.client_id == entry.client_id).all()}

    criterion_rows = []
    total_weight = 0
    weighted_sum = 0.0
    for s in scores:
        crit = criteria.get(s.criterion_id)
        if not crit:
            continue
        normalized = (s.score or 0) / 5.0
        contribution = normalized * crit.weight
        criterion_rows.append({
            "name": crit.name,
            "score": s.score,
            "weight": crit.weight,
            "contribution": round(contribution, 2),
            "reasoning": s.reasoning or "",
        })
        total_weight += crit.weight
        weighted_sum += contribution

    pmf_computed = round((weighted_sum / total_weight) * 100, 1) if total_weight > 0 else 0.0

    pmf_weight = entry.pmf_weight or 0.6
    rs_weight = entry.rs_weight or 0.4
    pmf_contrib = round((entry.pmf_score or 0) * pmf_weight, 1)
    rs_contrib = round(((entry.relationship_score or 0) / 5.0 * 100) * rs_weight, 1)
    base_score = round(pmf_contrib + rs_contrib, 1)

    friction = entry.friction_coefficient if entry.friction_coefficient is not None else 1.0
    intent = entry.intent_multiplier if entry.intent_multiplier is not None else 1.0

    # Sort criteria by contribution desc so biggest levers show first
    criterion_rows.sort(key=lambda r: r["contribution"], reverse=True)

    return {
        "entry_id": entry.id,
        "prospect_name": entry.prospect.name if entry.prospect else None,
        "tier": entry.tier,
        "matchmaker_score": entry.matchmaker_score,
        "filtered": bool(entry.filtered),
        "filter_reason": entry.filter_reason,
        "pmf": {
            "score": entry.pmf_score,
            "weight": pmf_weight,
            "contribution": pmf_contrib,
            "criteria": criterion_rows,
            "criteria_count": len(criterion_rows),
            "max_weight": total_weight,
        },
        "rs": {
            "score": entry.relationship_score,
            "weight": rs_weight,
            "contribution": rs_contrib,
        },
        "base_score": base_score,
        "friction": round(friction, 2),
        "intent": round(intent, 2),
        "formula": f"({pmf_contrib} + {rs_contrib}) × {round(friction,2)} × {round(intent,2)} = {entry.matchmaker_score}",
    }


@router.get("/{entry_id}/scores", response_model=List[CriterionScoreOut])
def get_criterion_scores(entry_id: int, db: Session = Depends(get_db)):
    """Get all criterion scores for a pipeline entry."""
    scores = (
        db.query(CriterionScore)
        .filter(CriterionScore.pipeline_entry_id == entry_id)
        .all()
    )
    result = []
    for s in scores:
        criterion = db.query(ScoringCriterion).filter(ScoringCriterion.id == s.criterion_id).first()
        result.append({
            "id": s.id,
            "criterion_id": s.criterion_id,
            "score": s.score,
            "reasoning": s.reasoning,
            "criterion_name": criterion.name if criterion else None,
            "criterion_weight": criterion.weight if criterion else None,
        })
    return result


@router.put("/{entry_id}/scores/{criterion_id}")
def override_criterion_score(entry_id: int, criterion_id: int, score: int, reasoning: str = None, db: Session = Depends(get_db)):
    """
    Manually override a single criterion score (0-5).
    Automatically recalculates PMF and Matchmaker Score for this entry.
    """
    score = max(0, min(5, int(score)))

    entry = db.query(PipelineEntry).filter(PipelineEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Pipeline entry not found")

    # Upsert the criterion score
    existing = (
        db.query(CriterionScore)
        .filter(CriterionScore.pipeline_entry_id == entry_id, CriterionScore.criterion_id == criterion_id)
        .first()
    )

    old_score = existing.score if existing else None
    new_reasoning = reasoning or f"Manual override (was {old_score if old_score is not None else 'unscored'})"

    if existing:
        existing.score = score
        existing.reasoning = new_reasoning
    else:
        cs = CriterionScore(
            pipeline_entry_id=entry_id,
            criterion_id=criterion_id,
            score=score,
            reasoning=new_reasoning,
        )
        db.add(cs)

    db.flush()

    # Recalculate PMF using all criterion scores for this entry
    all_scores = db.query(CriterionScore).filter(CriterionScore.pipeline_entry_id == entry_id).all()
    scores_and_weights = []
    for cs in all_scores:
        criterion = db.query(ScoringCriterion).filter(ScoringCriterion.id == cs.criterion_id).first()
        if criterion and criterion.active:
            scores_and_weights.append((cs.score, criterion.weight))

    pmf = calculate_pmf(scores_and_weights) if scores_and_weights else 0.0
    friction = entry.friction_coefficient or 1.0
    intent = entry.intent_multiplier or 1.0
    ms = calculate_matchmaker(pmf, entry.relationship_score, friction, intent)

    entry.pmf_score = round(pmf, 1)
    entry.matchmaker_score = round(ms, 1)
    old_tier = entry.tier
    entry.tier = assign_tier(ms, entry.filtered)
    entry.status = "scored"
    entry.updated_at = datetime.utcnow()

    # Log activity
    log = ActivityLog(
        pipeline_entry_id=entry_id,
        action="score_overridden",
        old_value=str(old_score) if old_score is not None else "unscored",
        new_value=str(score),
        notes=f"PMF: {entry.pmf_score}, MS: {entry.matchmaker_score}, Tier: {old_tier} -> {entry.tier}",
    )
    db.add(log)

    db.commit()
    db.refresh(entry)

    return {
        "criterion_id": criterion_id,
        "old_score": old_score,
        "new_score": score,
        "pmf_score": entry.pmf_score,
        "matchmaker_score": entry.matchmaker_score,
        "tier": entry.tier,
        "tier_changed": old_tier != entry.tier,
    }
