from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BehaviorProfile, Prospect
from app.schemas import BehaviorProfileCreate, BehaviorProfileOut

router = APIRouter(prefix="/api/behavior", tags=["behavior"])


# ============ TYPE-BASED HEURISTIC MAPPING ============
# Behavior profile defaults inferred from company type.
# Used by bulk-infer endpoint to auto-populate prospects without profiles.

TYPE_BEHAVIOR_MAP = {
    "Regional Carrier": {
        "sales_motion": "consultative",
        "partner_model": "managed",
        "decision_speed": "moderate",
        "culture": "balanced",
        "customer_segment": "SMB",
    },
    "National Carrier": {
        "sales_motion": "enterprise",
        "partner_model": "managed",
        "decision_speed": "bureaucratic",
        "culture": "legacy",
        "customer_segment": "mid-market",
    },
    "Specialty Carrier": {
        "sales_motion": "consultative",
        "partner_model": "managed",
        "decision_speed": "moderate",
        "culture": "balanced",
        "customer_segment": "SMB",
    },
    "National Brokerage": {
        "sales_motion": "consultative",
        "partner_model": "co-sell",
        "decision_speed": "bureaucratic",
        "culture": "balanced",
        "customer_segment": "mid-market",
    },
    "National Agency": {
        "sales_motion": "transactional",
        "partner_model": "managed",
        "decision_speed": "moderate",
        "culture": "balanced",
        "customer_segment": "SMB",
    },
    "Wholesale Broker": {
        "sales_motion": "consultative",
        "partner_model": "co-sell",
        "decision_speed": "moderate",
        "culture": "balanced",
        "customer_segment": "mid-market",
    },
    "Technology": {
        "sales_motion": "consultative",
        "partner_model": "self-serve",
        "decision_speed": "fast",
        "culture": "innovation-forward",
        "customer_segment": "mid-market",
    },
    "Marketplace": {
        "sales_motion": "transactional",
        "partner_model": "self-serve",
        "decision_speed": "fast",
        "culture": "innovation-forward",
        "customer_segment": "SMB",
    },
    "MGA": {
        "sales_motion": "consultative",
        "partner_model": "managed",
        "decision_speed": "moderate",
        "culture": "balanced",
        "customer_segment": "mid-market",
    },
}


@router.post("/bulk/infer")
def bulk_infer_behavior(db: Session = Depends(get_db)):
    """
    Auto-populate behavior profiles for all prospects that don't have one,
    using type-based heuristics. FREE - no Claude API calls.
    Returns count of profiles created and skipped.
    """
    prospects = db.query(Prospect).all()
    created = 0
    skipped_existing = 0
    skipped_no_type = 0

    for p in prospects:
        # Skip if already has a behavior profile
        existing = db.query(BehaviorProfile).filter(BehaviorProfile.prospect_id == p.id).first()
        if existing:
            skipped_existing += 1
            continue

        # Skip if no type (can't infer)
        if not p.type or p.type not in TYPE_BEHAVIOR_MAP:
            skipped_no_type += 1
            continue

        defaults = TYPE_BEHAVIOR_MAP[p.type]
        profile = BehaviorProfile(
            prospect_id=p.id,
            assessed_by="heuristic_bulk_infer",
            assessed_at=datetime.utcnow(),
            partnership_history=f"Auto-inferred from company type: {p.type}. Adjust manually for accuracy.",
            **defaults,
        )
        db.add(profile)
        created += 1

    db.commit()

    return {
        "created": created,
        "skipped_existing": skipped_existing,
        "skipped_no_type": skipped_no_type,
        "total_prospects": len(prospects),
    }


@router.get("/{prospect_id}", response_model=BehaviorProfileOut)
def get_behavior_profile(prospect_id: int, db: Session = Depends(get_db)):
    profile = db.query(BehaviorProfile).filter(BehaviorProfile.prospect_id == prospect_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No behavior profile found")
    return profile


@router.post("/{prospect_id}", response_model=BehaviorProfileOut)
def upsert_behavior_profile(prospect_id: int, data: BehaviorProfileCreate, db: Session = Depends(get_db)):
    """Create or update behavior profile (upsert)."""
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    profile = db.query(BehaviorProfile).filter(BehaviorProfile.prospect_id == prospect_id).first()

    if profile:
        for key, val in data.dict(exclude_unset=True).items():
            setattr(profile, key, val)
        profile.assessed_by = "manual"
        profile.assessed_at = datetime.utcnow()
        profile.updated_at = datetime.utcnow()
    else:
        profile = BehaviorProfile(
            prospect_id=prospect_id,
            assessed_by="manual",
            assessed_at=datetime.utcnow(),
            **data.dict(),
        )
        db.add(profile)

    db.commit()
    db.refresh(profile)
    return profile


@router.put("/{prospect_id}", response_model=BehaviorProfileOut)
def update_behavior_profile(prospect_id: int, data: BehaviorProfileCreate, db: Session = Depends(get_db)):
    """Update existing behavior profile."""
    profile = db.query(BehaviorProfile).filter(BehaviorProfile.prospect_id == prospect_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No behavior profile found. Use POST to create.")

    for key, val in data.dict(exclude_unset=True).items():
        setattr(profile, key, val)
    profile.assessed_by = "manual"
    profile.assessed_at = datetime.utcnow()
    profile.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(profile)
    return profile
