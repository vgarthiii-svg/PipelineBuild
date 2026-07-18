import csv
import io
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.database import get_db
from app.models import (
    PipelineEntry, Prospect, Client, ScoringCriterion,
    CriterionScore, Relationship, ActivityLog,
)
from app.schemas import (
    PipelineEntryCreate, PipelineEntryOut, PipelineWeightUpdate,
    PipelineBulkCreate, PipelineSummary, CriterionScoreCreate, CriterionScoreOut,
)
from app.scoring import calculate_pmf, calculate_matchmaker, assign_tier
from app.importers import ingest_pipeline_rows, import_decerto

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


@router.post("/import-decerto")
def import_decerto_pipeline(db: Session = Depends(get_db)):
    """Load the Decerto client + 52 scored carrier accounts from decerto_prospects.csv."""
    try:
        result = import_decerto(db)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "ok", "client": "Decerto", **result}


@router.post("/{client_id}/import-csv")
async def import_client_csv(
    client_id: int,
    file: UploadFile = File(...),
    source: str = Form("CSV import"),
    pmf_weight: float = Form(0.8),
    rs_weight: float = Form(0.2),
    db: Session = Depends(get_db),
):
    """
    Import an enriched prospect sheet into a client's pipeline, scored and ranked.

    Columns are auto-detected. Recognized headers include:
    Company/Partner Name/name, Segment/Partner Type/type, HQ, Fit, Contact, Signal,
    Outreach accelerant. A Fit column (1-5) drives the score; a WARM accelerant
    lifts relationship strength.
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    text = (await file.read()).decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    try:
        result = ingest_pipeline_rows(db, client, rows, source=source,
                                      pmf_weight=pmf_weight, rs_weight=rs_weight)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "client": client.name, **result}


@router.post("/quick-add")
def quick_add(client_id: int, company_name: str, db: Session = Depends(get_db)):
    """Add a single company by name. Creates prospect if needed, adds to pipeline."""
    company_name = company_name.strip()
    if not company_name:
        raise HTTPException(status_code=400, detail="Company name required")

    # Find or create prospect
    prospect = db.query(Prospect).filter(Prospect.name.ilike(company_name)).first()
    if not prospect:
        prospect = Prospect(name=company_name)
        db.add(prospect)
        db.flush()

    # Check for existing pipeline entry
    existing = db.query(PipelineEntry).filter(
        PipelineEntry.client_id == client_id,
        PipelineEntry.prospect_id == prospect.id,
    ).first()
    if existing:
        return _enrich_entry(existing, db)

    entry = PipelineEntry(
        client_id=client_id,
        prospect_id=prospect.id,
        source="Quick add",
    )
    best_rel = (
        db.query(Relationship)
        .filter(Relationship.prospect_id == prospect.id)
        .order_by(Relationship.score.desc())
        .first()
    )
    if best_rel:
        entry.relationship_score = best_rel.score

    db.add(entry)
    db.flush()

    log = ActivityLog(
        pipeline_entry_id=entry.id,
        action="added_to_pipeline",
        new_value=f"{company_name} added to pipeline",
        notes="Quick add",
    )
    db.add(log)
    db.commit()
    db.refresh(entry)
    return _enrich_entry(entry, db)


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
    """Recalculate Matchmaker Score for all entries using existing criterion scores."""
    entries = db.query(PipelineEntry).filter(PipelineEntry.client_id == client_id).all()
    results = []

    for entry in entries:
        criterion_scores = (
            db.query(CriterionScore)
            .filter(CriterionScore.pipeline_entry_id == entry.id)
            .all()
        )
        scores_and_weights = []
        for cs in criterion_scores:
            criterion = db.query(ScoringCriterion).filter(ScoringCriterion.id == cs.criterion_id).first()
            if criterion:
                scores_and_weights.append((cs.score, criterion.weight))

        if scores_and_weights:
            pmf = calculate_pmf(scores_and_weights)
        elif entry.pmf_score is not None:
            pmf = entry.pmf_score
        else:
            pmf = 0.0

        matchmaker = calculate_matchmaker(pmf, entry.relationship_score, entry.pmf_weight, entry.rs_weight)
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

    scored = [e for e in entries if e.matchmaker_score is not None]
    avg_matchmaker = round(sum(e.matchmaker_score for e in scored) / len(scored), 1) if scored else None
    avg_pmf = round(sum(e.pmf_score for e in scored if e.pmf_score) / max(len([e for e in scored if e.pmf_score]), 1), 1) if scored else None
    avg_rs = round(sum(e.relationship_score for e in entries) / total, 1) if total else None

    return PipelineSummary(
        total=total, hot=hot, warm=warm, monitor=monitor,
        pass_count=pass_count, unscored=unscored,
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
