import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BusinessProfile, Prospect
from app.services import profile_generator

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("/{prospect_id}")
def get_profile(prospect_id: int, db: Session = Depends(get_db)):
    """Get the business profile for a prospect. Creates a heuristic one if missing."""
    profile = db.query(BusinessProfile).filter(BusinessProfile.prospect_id == prospect_id).first()
    if not profile:
        prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
        if not prospect:
            raise HTTPException(status_code=404, detail="Prospect not found")
        profile = profile_generator.upsert_profile(prospect, db, run_enrichment=False)
        db.commit()
    return _profile_dict(profile)


@router.post("/{prospect_id}/generate")
def generate_profile(prospect_id: int, depth: str = "basic", db: Session = Depends(get_db)):
    """
    Generate/upgrade a profile to the requested depth.
    depth: "basic" (Layer 1 free), "enriched" (Layer 2 free), "deep" (Layer 3 cost-gated).
    """
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    if depth == "deep":
        # Cost-gated
        from app.routers.notifications import create_pending_action
        action = create_pending_action(
            db,
            action_type="profile_client",
            description=f"Deep research profile for {prospect.name} via Claude AI. Generates products, competitors, value chain, and market position.",
            params={"prospect_id": prospect_id, "depth": "deep"},
            estimated_cost="$0.03-0.06",
        )
        return {
            "status": "pending_approval",
            "action_id": action.id,
            "message": f"Deep profile research for {prospect.name} requires your approval.",
        }

    # Free layers
    profile = profile_generator.upsert_profile(prospect, db, run_enrichment=(depth == "enriched"))
    db.commit()
    return _profile_dict(profile)


@router.post("/bulk/enrich")
def enrich_all(client_id: int = None, db: Session = Depends(get_db)):
    """
    Run Layer 1 + Layer 2 on all prospects (or all in a client's pipeline).
    Free if Apollo/HubSpot keys are set. No Claude API calls.
    """
    from app.models import PipelineEntry

    if client_id:
        entry_ids = db.query(PipelineEntry.prospect_id).filter(PipelineEntry.client_id == client_id).all()
        prospect_ids = [e[0] for e in entry_ids]
        prospects = db.query(Prospect).filter(Prospect.id.in_(prospect_ids)).all()
    else:
        prospects = db.query(Prospect).all()

    enriched = 0
    basic = 0
    for p in prospects:
        profile = profile_generator.upsert_profile(p, db, run_enrichment=True)
        if profile.generation_depth == "enriched":
            enriched += 1
        else:
            basic += 1

    db.commit()

    # Log notification
    from app.routers.notifications import create_notification
    create_notification(
        db,
        type="profile_enrichment",
        title=f"Bulk enrichment complete: {len(prospects)} companies",
        detail=f"{enriched} enriched (Apollo/HubSpot), {basic} basic heuristic. Zero API cost.",
    )

    return {
        "total": len(prospects),
        "enriched": enriched,
        "basic": basic,
        "message": f"Profiled {len(prospects)} companies. {enriched} via external sources, {basic} via heuristics.",
    }


@router.put("/{prospect_id}")
def update_profile(prospect_id: int, updates: dict, db: Session = Depends(get_db)):
    """Manually update a business profile (any field)."""
    profile = db.query(BusinessProfile).filter(BusinessProfile.prospect_id == prospect_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    for key, val in updates.items():
        if hasattr(profile, key):
            setattr(profile, key, val)

    profile.generated_by = "manual"
    profile.last_refreshed = datetime.utcnow()
    profile.confidence_score = min(100, (profile.confidence_score or 0) + 10)
    db.commit()
    db.refresh(profile)
    return _profile_dict(profile)


@router.get("/")
def list_profiles(limit: int = 100, db: Session = Depends(get_db)):
    """List all profiles with basic info for overview."""
    profiles = db.query(BusinessProfile).limit(limit).all()
    return [_profile_dict(p) for p in profiles]


def _profile_dict(p):
    if not p:
        return None
    return {
        "id": p.id,
        "prospect_id": p.prospect_id,
        "one_liner": p.one_liner,
        "long_description": p.long_description,
        "founded_year": p.founded_year,
        "headquarters": p.headquarters,
        "primary_products": _parse_json(p.primary_products),
        "secondary_products": _parse_json(p.secondary_products),
        "flagship_product": p.flagship_product,
        "target_customer_types": _parse_json(p.target_customer_types),
        "target_segments": _parse_json(p.target_segments),
        "target_verticals": _parse_json(p.target_verticals),
        "geographic_markets": _parse_json(p.geographic_markets),
        "sales_channels": _parse_json(p.sales_channels),
        "pricing_model": p.pricing_model,
        "typical_deal_size": p.typical_deal_size,
        "value_chain_upstream": _parse_json(p.value_chain_upstream),
        "value_chain_downstream": _parse_json(p.value_chain_downstream),
        "key_integrations": _parse_json(p.key_integrations),
        "main_competitors": _parse_json(p.main_competitors),
        "key_differentiators": p.key_differentiators,
        "market_position": p.market_position,
        "recent_developments": _parse_json(p.recent_developments),
        "growth_indicators": p.growth_indicators,
        "generated_by": p.generated_by,
        "generation_depth": p.generation_depth,
        "confidence_score": p.confidence_score,
        "last_refreshed": p.last_refreshed,
        "refresh_due": p.refresh_due,
    }


def _parse_json(val):
    if not val:
        return []
    if isinstance(val, list):
        return val
    try:
        return json.loads(val)
    except:
        return []
