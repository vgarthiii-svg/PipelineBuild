import json
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Client, ScoringCriterion, CriteriaLibrary, Prospect, PipelineEntry, Relationship
from app.schemas import ClientCreate, ClientOut, CriterionCreate, CriterionOut
from app.services import hubspot_scan, apollo_enrich

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("/", response_model=List[ClientOut])
def list_clients(db: Session = Depends(get_db)):
    return db.query(Client).order_by(Client.name).all()


@router.get("/lens-options")
def list_lens_options(db: Session = Depends(get_db)):
    """
    Return every company in the system as a potential "lens" for the pipeline.
    Any company (prospect) can be selected as the viewpoint; if it doesn't yet
    have a client record (criteria + pipeline), the frontend will auto-promote
    on selection.

    Sources from the prospects table (the canonical company pool). Merges in
    client data when a matching client record exists.
    """
    # Map client names to their records for fast lookup
    clients = db.query(Client).all()
    clients_by_name = {c.name.lower(): c for c in clients}

    options = []
    seen_names = set()

    # 1. Every prospect becomes a potential lens option
    for p in db.query(Prospect).order_by(Prospect.name).all():
        key = p.name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        client = clients_by_name.get(key)
        options.append({
            "prospect_id": p.id,
            "name": p.name,
            "client_id": client.id if client else None,
            "has_client_record": client is not None,
            "active": bool(client.active) if client and client.active else False,
            "type": p.type,
            "description": p.description or (client.description if client else ""),
        })

    # 2. Add orphan clients (clients without a matching prospect) — shouldn't happen after sync, but be safe
    for c in clients:
        if c.name.lower() in seen_names:
            continue
        options.append({
            "prospect_id": None,
            "name": c.name,
            "client_id": c.id,
            "has_client_record": True,
            "active": bool(c.active) if c.active else False,
            "type": None,
            "description": c.description or "",
        })

    # Sort: active clients first, then everything else alphabetically
    options.sort(key=lambda o: (0 if o["active"] else (1 if o["has_client_record"] else 2), o["name"].lower()))
    return options


@router.put("/{client_id}/toggle-active")
def toggle_active(client_id: int, db: Session = Depends(get_db)):
    """Toggle a client between active and inactive status."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    new_active = not bool(client.active)
    client.active = new_active
    db.commit()
    db.refresh(client)
    return {"id": client.id, "name": client.name, "active": new_active}


@router.get("/criteria-counts")
def get_criteria_counts(db: Session = Depends(get_db)):
    """Return a map of client_id -> number of scoring criteria."""
    clients = db.query(Client).all()
    return {
        c.id: db.query(ScoringCriterion).filter(ScoringCriterion.client_id == c.id).count()
        for c in clients
    }


@router.post("/", response_model=ClientOut)
def create_client(data: ClientCreate, db: Session = Depends(get_db)):
    client = Client(**data.dict())
    db.add(client)
    db.commit()
    db.refresh(client)

    # 1. Add every existing prospect into this client's NEW pipeline
    _add_all_prospects_to_pipeline(client.id, db)
    # 2. Ensure prospect + profile exist AND add this new client into every OTHER client's pipeline
    _sync_new_client_to_all_pipelines(client, db)
    db.commit()
    return client


@router.get("/search")
def search_client_sources(q: str, db: Session = Depends(get_db)):
    """
    Search HubSpot and Apollo in parallel for companies matching the query.
    Returns combined results tagged by source for the client selector UI.
    """
    if not q or len(q) < 2:
        return {"hubspot": {"available": False, "results": []}, "apollo": {"available": False, "results": []}}

    hs_result = hubspot_scan.search_companies(q, limit=5)
    ap_result = apollo_enrich.search_organizations(q, limit=5)

    return {
        "hubspot": hs_result,
        "apollo": ap_result,
    }


@router.post("/from-source")
def create_client_from_source(
    name: str,
    source: str = "manual",
    domain: str = "",
    description: str = "",
    city: str = "",
    state: str = "",
    industry: str = "",
    employees: str = "",
    revenue: str = "",
    phone: str = "",
    hubspot_id: str = "",
    db: Session = Depends(get_db),
):
    """
    Create a client from a HubSpot/Apollo search result or manual entry.
    Pre-populates with source data, then runs Claude profiling + criteria generation.
    """
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Company name required")

    # Check if already exists
    existing = db.query(Client).filter(Client.name.ilike(name)).first()
    if existing:
        criteria = (
            db.query(ScoringCriterion)
            .filter(ScoringCriterion.client_id == existing.id)
            .order_by(ScoringCriterion.sort_order)
            .all()
        )
        return {
            "client": _client_dict(existing),
            "criteria": [_criterion_dict(c) for c in criteria],
            "researched": False,
            "message": f"{name} already exists as a client.",
        }

    # If HubSpot source, fetch associated contacts
    hs_contacts = []
    if source == "hubspot" and hubspot_id:
        hs_contacts = hubspot_scan.get_company_contacts(hubspot_id)

    # Create client with pre-populated data
    new_client = Client(
        name=name,
        website=domain if domain else "",
        description=description,
        target_buyer="",
        primary_revenue_driver="",
        profile_json=json.dumps({
            "source": source,
            "domain": domain,
            "city": city,
            "state": state,
            "industry": industry,
            "employees": employees,
            "revenue": revenue,
            "phone": phone,
            "hubspot_id": hubspot_id,
            "hs_contacts": hs_contacts,
        }),
    )
    db.add(new_client)
    db.flush()

    # FREE PATH: Use source data + default criteria, NO Claude API call.
    # User can explicitly trigger Deep Research via the Refresh menu for a richer profile.
    profile_data = None
    criteria_data = None

    # Use Claude criteria if available, otherwise generate defaults
    criteria_list = criteria_data or _generate_default_criteria(name, new_client.description or "")

    created_criteria = []
    for i, c in enumerate(criteria_list):
        criterion = ScoringCriterion(
            client_id=new_client.id,
            name=c.get("name", f"Criterion {i+1}"),
            description=c.get("description", ""),
            why_it_matters=c.get("why_it_matters", ""),
            weight=min(max(int(c.get("weight", 5)), 1), 10),
            sort_order=c.get("sort_order", i + 1),
        )
        db.add(criterion)
        db.flush()
        created_criteria.append(criterion)

    # Add all existing prospects to this client's pipeline
    prospects_added = _add_all_prospects_to_pipeline(new_client.id, db)
    # And add this new client as a prospect in every other client's pipeline
    _sync_new_client_to_all_pipelines(new_client, db)
    db.commit()

    # Auto-score all entries with heuristics (free, instant)
    scored_count = _auto_score_pipeline(new_client.id, db)
    db.commit()

    db.refresh(new_client)

    return {
        "client": _client_dict(new_client),
        "criteria": [_criterion_dict(c) for c in created_criteria],
        "researched": bool(profile_data),
        "source": source,
        "prospects_added": prospects_added,
        "scored": scored_count,
        "message": f"Created {name} with {len(created_criteria)} criteria. {prospects_added} companies added and {scored_count} scored.",
    }


@router.post("/promote/{prospect_id}")
def promote_prospect_to_client(prospect_id: int, db: Session = Depends(get_db)):
    """
    Promote an existing prospect to a client. Copies prospect data,
    runs Claude profiling, and generates scoring criteria.
    """
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    # Check if already a client
    existing = db.query(Client).filter(Client.name.ilike(prospect.name)).first()
    if existing:
        criteria = (
            db.query(ScoringCriterion)
            .filter(ScoringCriterion.client_id == existing.id)
            .order_by(ScoringCriterion.sort_order)
            .all()
        )
        return {
            "client": _client_dict(existing),
            "criteria": [_criterion_dict(c) for c in criteria],
            "researched": False,
            "message": f"{prospect.name} is already a client.",
        }

    # Pull business profile data if available
    from app.models import BusinessProfile
    from app.services import profile_generator
    from datetime import datetime
    bp = db.query(BusinessProfile).filter(BusinessProfile.prospect_id == prospect.id).first()
    if not bp:
        # Generate one now (free, heuristic + enrichment)
        bp = profile_generator.upsert_profile(prospect, db, run_enrichment=True)
        db.flush()
    else:
        # Client is being promoted with existing profile - bump last_refreshed so the UI knows the data is current
        bp.last_refreshed = datetime.utcnow()
        db.flush()

    # Derive client fields from business profile
    desc = prospect.description or ""
    if bp and bp.long_description:
        desc = bp.long_description
    elif bp and bp.one_liner:
        desc = bp.one_liner

    target_buyer = ""
    if bp and bp.target_customer_types:
        try:
            customer_types = json.loads(bp.target_customer_types)
            if isinstance(customer_types, list):
                target_buyer = ", ".join(customer_types)
        except (json.JSONDecodeError, TypeError):
            pass

    primary_driver = ""
    if bp and bp.flagship_product:
        primary_driver = bp.flagship_product
    elif bp and bp.primary_products:
        try:
            products = json.loads(bp.primary_products)
            if isinstance(products, list) and products:
                primary_driver = ", ".join(products[:3])
        except (json.JSONDecodeError, TypeError):
            pass

    # Create client from prospect + profile data
    new_client = Client(
        name=prospect.name,
        website=prospect.website or prospect.domain or "",
        description=desc,
        target_buyer=target_buyer,
        primary_revenue_driver=primary_driver,
        profile_json=json.dumps({
            "source": "promoted_from_prospect",
            "prospect_id": prospect.id,
            "type": prospect.type,
            "domain": prospect.domain,
            "hq_city": prospect.hq_city,
            "hq_state": prospect.hq_state,
            "employees": prospect.employees,
            "revenue": prospect.revenue,
        }),
    )
    db.add(new_client)
    db.flush()

    # FREE PATH: Use default criteria from company type (no Claude API call).
    # User can explicitly trigger Deep Research afterward via the Refresh menu.
    profile_data = None
    criteria_data = None
    criteria_list = _generate_default_criteria(prospect.name, new_client.description or "")

    created_criteria = []
    for i, c in enumerate(criteria_list):
        criterion = ScoringCriterion(
            client_id=new_client.id,
            name=c.get("name", f"Criterion {i+1}"),
            description=c.get("description", ""),
            why_it_matters=c.get("why_it_matters", ""),
            weight=min(max(int(c.get("weight", 5)), 1), 10),
            sort_order=c.get("sort_order", i + 1),
        )
        db.add(criterion)
        db.flush()
        created_criteria.append(criterion)

    # Add all existing prospects to this client's pipeline
    prospects_added = _add_all_prospects_to_pipeline(new_client.id, db)
    db.commit()

    # Auto-score all entries with heuristics (free, instant)
    scored_count = _auto_score_pipeline(new_client.id, db)
    db.commit()

    db.refresh(new_client)

    return {
        "client": _client_dict(new_client),
        "criteria": [_criterion_dict(c) for c in created_criteria],
        "researched": bool(profile_data),
        "prospects_added": prospects_added,
        "scored": scored_count,
        "promoted_from_prospect": True,
        "message": f"{prospect.name} promoted to client with {len(created_criteria)} criteria. {prospects_added} companies added and {scored_count} scored.",
    }


def _coerce_to_string(value, default=""):
    """Coerce a value to a string. Handles dicts, lists, None safely."""
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        # Concatenate dict values into a readable string
        parts = [f"{k}: {v}" for k, v in value.items() if v]
        return " | ".join(parts)
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _queue_deep_research(client, db):
    """
    Auto-queue a deep research pending action for a newly created client.
    Does nothing if Anthropic key not set.
    Returns the action_id if queued, None otherwise.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    # Find or create the matching prospect record
    prospect = db.query(Prospect).filter(Prospect.name.ilike(client.name)).first()
    if not prospect:
        # Create a minimal prospect record so deep research has a target
        prospect = Prospect(name=client.name, website=client.website, description=client.description)
        db.add(prospect)
        db.flush()

    from app.routers.notifications import create_pending_action
    action = create_pending_action(
        db,
        action_type="profile_client",
        description=f"Deep research profile for {client.name} via Claude AI. Will populate products, value chain, competitors, market position, and recent developments.",
        params={"prospect_id": prospect.id, "depth": "deep"},
        estimated_cost="$0.03-0.06",
    )
    return action.id


def _client_dict(c):
    return {
        "id": c.id, "name": c.name, "description": c.description,
        "primary_revenue_driver": c.primary_revenue_driver,
        "target_buyer": c.target_buyer, "website": c.website,
        "active": bool(c.active) if hasattr(c, 'active') and c.active else False,
    }


def _criterion_dict(c):
    return {
        "id": c.id, "name": c.name, "description": c.description,
        "why_it_matters": c.why_it_matters, "weight": c.weight,
        "sort_order": c.sort_order, "client_id": c.client_id,
    }


def _sync_new_client_to_all_pipelines(new_client, db):
    """
    When a new client is created, ensure a matching prospect record exists
    and add that prospect to every OTHER client's pipeline.
    Then rescore those pipelines so the new company appears with a Matchmaker Score.
    """
    from app.services import profile_generator, type_inference
    from app.routers.behavior import TYPE_BEHAVIOR_MAP
    from app.models import BehaviorProfile
    from datetime import datetime

    # 1. Ensure prospect record exists with a type
    prospect = db.query(Prospect).filter(Prospect.name.ilike(new_client.name)).first()
    if not prospect:
        inferred_type = type_inference.infer_type(
            name=new_client.name,
            description=new_client.description or "",
            domain=new_client.website or "",
        )
        prospect = Prospect(
            name=new_client.name,
            website=new_client.website,
            description=new_client.description,
            type=inferred_type,
        )
        db.add(prospect)
        db.flush()
    elif not prospect.type:
        prospect.type = type_inference.infer_type(
            name=prospect.name,
            description=prospect.description or "",
            domain=prospect.domain or prospect.website or "",
        )

    # 2. Ensure business profile + behavior profile exist
    profile_generator.upsert_profile(prospect, db, run_enrichment=True)

    if prospect.type and prospect.type in TYPE_BEHAVIOR_MAP:
        existing_bp = db.query(BehaviorProfile).filter(BehaviorProfile.prospect_id == prospect.id).first()
        if not existing_bp:
            defaults = TYPE_BEHAVIOR_MAP[prospect.type]
            bp = BehaviorProfile(
                prospect_id=prospect.id,
                assessed_by="heuristic_auto",
                assessed_at=datetime.utcnow(),
                partnership_history=f"Auto-inferred from type: {prospect.type}.",
                **defaults,
            )
            db.add(bp)

    # 3. Add this new client's prospect record to every OTHER client's pipeline
    best_rel = (
        db.query(Relationship)
        .filter(Relationship.prospect_id == prospect.id)
        .order_by(Relationship.score.desc())
        .first()
    )
    all_clients = db.query(Client).filter(Client.id != new_client.id).all()
    added_to = []
    for cl in all_clients:
        existing = db.query(PipelineEntry).filter(
            PipelineEntry.client_id == cl.id,
            PipelineEntry.prospect_id == prospect.id,
        ).first()
        if existing:
            continue
        entry = PipelineEntry(
            client_id=cl.id,
            prospect_id=prospect.id,
            source="Auto-added on new client creation",
        )
        if best_rel:
            entry.relationship_score = best_rel.score
        db.add(entry)
        added_to.append(cl.id)

    db.flush()

    # 4. Rescore all the pipelines that got the new prospect
    for cid in added_to:
        _auto_score_pipeline(cid, db)

    return len(added_to)


def _add_all_prospects_to_pipeline(client_id: int, db):
    """Add every prospect in the database to this client's pipeline."""
    all_prospects = db.query(Prospect).all()
    added = 0
    for p in all_prospects:
        # Skip if already in pipeline for this client
        existing = db.query(PipelineEntry).filter(
            PipelineEntry.client_id == client_id,
            PipelineEntry.prospect_id == p.id,
        ).first()
        if existing:
            continue

        # Don't add the client itself as a prospect in its own pipeline
        client = db.query(Client).filter(Client.id == client_id).first()
        if client and p.name.lower() == client.name.lower():
            continue

        entry = PipelineEntry(
            client_id=client_id,
            prospect_id=p.id,
            source="Auto-added on client creation",
        )
        # Carry over best relationship score
        best_rel = (
            db.query(Relationship)
            .filter(Relationship.prospect_id == p.id)
            .order_by(Relationship.score.desc())
            .first()
        )
        if best_rel:
            entry.relationship_score = best_rel.score

        db.add(entry)
        added += 1

    db.flush()
    return added


def _auto_score_pipeline(client_id: int, db):
    """
    Auto-score all pipeline entries using heuristic scoring (free, instant).
    Uses prospect metadata (type, industry, business model, stage, description)
    to infer criterion scores. No API calls. No cost.
    """
    from app.models import CriterionScore, BehaviorProfile, IntentSignal, IdentityFilter
    from app.scoring import (
        calculate_pmf, calculate_matchmaker, assign_tier,
        heuristic_score_prospect, run_identity_filter,
        calculate_friction_coefficient, calculate_intent_multiplier,
    )

    client = db.query(Client).filter(Client.id == client_id).first()
    criteria = db.query(ScoringCriterion).filter(ScoringCriterion.client_id == client_id, ScoringCriterion.active == True).all()

    if not client or not criteria:
        return 0

    entries = db.query(PipelineEntry).filter(PipelineEntry.client_id == client_id).all()
    scored = 0

    # Load client context for 4-layer scoring
    client_filter = db.query(IdentityFilter).filter(IdentityFilter.client_id == client_id).first()
    client_prospect = db.query(Prospect).filter(Prospect.name.ilike(client.name)).first()
    client_behavior = None
    if client_prospect:
        client_behavior = db.query(BehaviorProfile).filter(BehaviorProfile.prospect_id == client_prospect.id).first()

    for entry in entries:
        prospect = db.query(Prospect).filter(Prospect.id == entry.prospect_id).first()
        if not prospect:
            continue

        # Skip if already scored
        existing_scores = db.query(CriterionScore).filter(CriterionScore.pipeline_entry_id == entry.id).count()
        if existing_scores > 0:
            scored += 1
            continue

        # Layer 1: Identity filter
        passed, reason = run_identity_filter(prospect, client_filter)
        if not passed:
            entry.filtered = True
            entry.filter_reason = reason
            entry.tier = "filtered"
            entry.status = "scored"
            scored += 1
            continue
        else:
            entry.filtered = False
            entry.filter_reason = None

        # Layer 2: Heuristic criterion scoring (FREE)
        heuristic_results = heuristic_score_prospect(prospect, client, criteria)

        scores_and_weights = []
        for h in heuristic_results:
            cs = CriterionScore(
                pipeline_entry_id=entry.id,
                criterion_id=h["criterion_id"],
                score=h["score"],
                reasoning=h["reasoning"],
            )
            db.add(cs)
            crit = next((c for c in criteria if c.id == h["criterion_id"]), None)
            if crit:
                scores_and_weights.append((h["score"], crit.weight))

        pmf = calculate_pmf(scores_and_weights) if scores_and_weights else 0.0

        # Layer 3: Friction
        prospect_behavior = db.query(BehaviorProfile).filter(BehaviorProfile.prospect_id == entry.prospect_id).first()
        friction = calculate_friction_coefficient(client_behavior, prospect_behavior)
        entry.friction_coefficient = friction

        # Layer 4: Intent
        intent_signals = db.query(IntentSignal).filter(IntentSignal.prospect_id == entry.prospect_id).all()
        intent = calculate_intent_multiplier(intent_signals)
        entry.intent_multiplier = intent

        # Calculate final score
        ms = calculate_matchmaker(pmf, entry.relationship_score, friction, intent)
        entry.pmf_score = round(pmf, 1)
        entry.matchmaker_score = round(ms, 1)
        entry.tier = assign_tier(ms)
        entry.status = "scored"
        scored += 1

    db.flush()
    return scored


def _run_claude_profiling(name, description, domain):
    """Run Claude API profiling and criteria generation. Returns (profile_data, criteria_data)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, None

    profile_data = None
    criteria_data = None

    try:
        import anthropic
        client_ai = anthropic.Anthropic(api_key=api_key)

        context = f"{name}"
        if description:
            context += f" - {description}"
        if domain:
            context += f" ({domain})"

        # Step 1: Profile
        profile_resp = client_ai.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            system="""You are a B2B business development analyst specializing in the INSURANCE INDUSTRY.
The company being researched is either an insurance carrier, MGA, brokerage, agency, wholesale broker,
insurtech, or insurance-adjacent technology/service vendor. Default to the insurance context when a
company name is ambiguous (e.g., 'NatGen' = National General Insurance, 'Guard' = Guard Insurance,
'Flex' = fintech/insurance platform, 'Shelter' = Shelter Insurance). Research this company and return
a structured profile as valid JSON only.""",
            messages=[{
                "role": "user",
                "content": f"""Research {context} (INSURANCE INDUSTRY company) and return JSON with these exact keys:
- description: What the company does (2-3 sentences) - insurance context
- primary_revenue_driver: Their main product or service (1 sentence) - must be a plain STRING not a dict
- target_buyer: Who they sell to - must be a plain STRING not a dict (e.g., "Independent agencies, MGAs, and specialty brokers in the P&C market")
- website: Company website URL
- products: Array of their key insurance products/services
- problems_solved: Array of 3 insurance-industry problems they solve for customers
- value_chain_upstream: Array of what customers need BEFORE this product
- value_chain_downstream: Array of what customers need AFTER this product

Remember: primary_revenue_driver and target_buyer must be plain strings, not objects/dicts."""
            }],
        )
        text = profile_resp.content[0].text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        profile_data = json.loads(text.strip())

        # Step 2: Criteria
        criteria_resp = client_ai.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1500,
            system="""You generate scoring criteria for evaluating partner companies against a target client.
Rules: Generate exactly 4-6 criteria. Each measures how well a prospect fits as a partner.
Weight each 1-10. Include buyer alignment and product complementarity criteria.
Return valid JSON only.""",
            messages=[{
                "role": "user",
                "content": f"""Generate scoring criteria for evaluating partner companies for {name}.
Company profile: {json.dumps(profile_data, indent=2)}
Return JSON array: [{{"name": "...", "description": "...", "why_it_matters": "...", "weight": N, "sort_order": N}}]"""
            }],
        )
        text = criteria_resp.content[0].text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        criteria_data = json.loads(text.strip())

    except Exception as e:
        print(f"[CLIENT RESEARCH] Claude API error: {e}")

    return profile_data, criteria_data


def _generate_default_criteria(name, description=""):
    """
    Generate sensible default scoring criteria when Claude API is unavailable.
    Returns a list of criterion dicts ready to insert.
    """
    desc_lower = (description or "").lower()
    name_lower = name.lower()

    # Detect company type from description/name
    is_insurance = any(kw in desc_lower or kw in name_lower for kw in ["insurance", "carrier", "underwriting", "policy", "claims"])
    is_tech = any(kw in desc_lower or kw in name_lower for kw in ["technology", "saas", "software", "platform", "ai", "digital"])
    is_fintech = any(kw in desc_lower or kw in name_lower for kw in ["fintech", "payment", "billing", "finance"])

    criteria = [
        {
            "name": "Product Complementarity",
            "description": f"Does this prospect's product naturally complement {name}'s offering?",
            "why_it_matters": f"Partners whose products pair with {name} create stronger value propositions",
            "weight": 5,
            "sort_order": 1,
        },
        {
            "name": "Buyer Alignment",
            "description": f"Does this prospect sell to the same buyer type as {name}?",
            "why_it_matters": "Shared buyer type means warm introductions carry more weight",
            "weight": 5,
            "sort_order": 2,
        },
        {
            "name": "Market Segment Fit",
            "description": f"Does this prospect operate in the same market segment as {name}'s customers?",
            "why_it_matters": "Segment alignment drives conversion on introductions",
            "weight": 4,
            "sort_order": 3,
        },
        {
            "name": "Channel Compatibility",
            "description": f"Could this prospect benefit from or contribute to {name}'s distribution channels?",
            "why_it_matters": "Channel overlap creates mutual referral opportunities",
            "weight": 4,
            "sort_order": 4,
        },
    ]

    # Add industry-specific criteria
    if is_insurance:
        criteria.append({
            "name": "Distribution Alignment",
            "description": "Does this prospect work in policy/underwriting/distribution vs. claims-only?",
            "why_it_matters": "Distribution-focused partners are stronger fits for growth partnerships",
            "weight": 5,
            "sort_order": 5,
        })
    elif is_tech:
        criteria.append({
            "name": "Technology Integration Potential",
            "description": "Could this prospect integrate with or enhance the tech platform?",
            "why_it_matters": "Tech partnerships create stickier relationships through integration",
            "weight": 5,
            "sort_order": 5,
        })
    else:
        criteria.append({
            "name": "Strategic Value",
            "description": f"Does this prospect bring strategic value beyond a single transaction to {name}?",
            "why_it_matters": "Long-term strategic partners compound over time",
            "weight": 4,
            "sort_order": 5,
        })

    return criteria


@router.post("/research")
def research_and_create_client(name: str, db: Session = Depends(get_db)):
    """
    Create a new client by name. If Claude API key is set, auto-research
    the company and generate scoring criteria. Returns the client with
    generated profile and criteria.
    """
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Company name required")

    # Check if already exists
    existing = db.query(Client).filter(Client.name.ilike(name)).first()
    if existing:
        criteria = (
            db.query(ScoringCriterion)
            .filter(ScoringCriterion.client_id == existing.id)
            .order_by(ScoringCriterion.sort_order)
            .all()
        )
        return {
            "client": {
                "id": existing.id,
                "name": existing.name,
                "description": existing.description,
                "primary_revenue_driver": existing.primary_revenue_driver,
                "target_buyer": existing.target_buyer,
                "website": existing.website,
            },
            "criteria": [
                {"id": c.id, "name": c.name, "description": c.description,
                 "why_it_matters": c.why_it_matters, "weight": c.weight,
                 "sort_order": c.sort_order, "client_id": c.client_id}
                for c in criteria
            ],
            "researched": False,
            "message": f"{name} already exists as a client.",
        }

    # FREE PATH: No Claude API call. Use default criteria.
    # User can trigger Deep Research via the Refresh menu for AI-powered profile.
    profile_data = None
    criteria_data = _generate_default_criteria(name, "")

    # Create the client
    new_client = Client(name=name)
    db.add(new_client)
    db.flush()

    # Create default criteria
    created_criteria = []
    for i, c in enumerate(criteria_data):
        criterion = ScoringCriterion(
            client_id=new_client.id,
            name=c.get("name", f"Criterion {i+1}"),
            description=c.get("description", ""),
            why_it_matters=c.get("why_it_matters", ""),
            weight=min(max(int(c.get("weight", 5)), 1), 10),
            sort_order=c.get("sort_order", i + 1),
        )
        db.add(criterion)
        db.flush()
        created_criteria.append(criterion)

    # Add all existing prospects to this client's pipeline
    _add_all_prospects_to_pipeline(new_client.id, db)
    # Sync: ensure prospect+profile exist AND add this client to every other client's pipeline
    _sync_new_client_to_all_pipelines(new_client, db)

    db.commit()
    db.refresh(new_client)

    return {
        "client": {
            "id": new_client.id,
            "name": new_client.name,
            "description": new_client.description,
            "primary_revenue_driver": new_client.primary_revenue_driver,
            "target_buyer": new_client.target_buyer,
            "website": new_client.website,
        },
        "criteria": [
            {"id": c.id, "name": c.name, "description": c.description,
             "why_it_matters": c.why_it_matters, "weight": c.weight,
             "sort_order": c.sort_order, "client_id": c.client_id}
            for c in created_criteria
        ],
        "researched": bool(profile_data),
        "message": f"{'Researched and created' if profile_data else 'Created'} {name} with {len(created_criteria)} scoring criteria.",
    }


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.put("/{client_id}", response_model=ClientOut)
def update_client(client_id: int, data: ClientCreate, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for key, val in data.dict(exclude_unset=True).items():
        setattr(client, key, val)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}")
def delete_client(client_id: int, db: Session = Depends(get_db)):
    from app.models import CriterionScore, IntroPackage, ActivityLog as AL, IdentityFilter

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Cascade delete: criteria, identity filters, pipeline entries and their children
    db.query(ScoringCriterion).filter(ScoringCriterion.client_id == client_id).delete()
    db.query(IdentityFilter).filter(IdentityFilter.client_id == client_id).delete()

    # Pipeline entries and their children (criterion_scores, intro_packages, activity_logs)
    entry_ids = [e.id for e in db.query(PipelineEntry.id).filter(PipelineEntry.client_id == client_id).all()]
    if entry_ids:
        db.query(CriterionScore).filter(CriterionScore.pipeline_entry_id.in_(entry_ids)).delete(synchronize_session=False)
        db.query(IntroPackage).filter(IntroPackage.pipeline_entry_id.in_(entry_ids)).delete(synchronize_session=False)
        db.query(AL).filter(AL.pipeline_entry_id.in_(entry_ids)).delete(synchronize_session=False)
        db.query(PipelineEntry).filter(PipelineEntry.client_id == client_id).delete(synchronize_session=False)

    name = client.name
    client_website = client.website
    client_description = client.description
    db.delete(client)
    db.flush()

    # Option B: the company remains as a prospect in every other client's pipeline.
    # Ensure the prospect record exists and is present in all remaining clients' pipelines,
    # so nothing "disappears" when a client is demoted.
    prospect = db.query(Prospect).filter(Prospect.name.ilike(name)).first()
    if not prospect:
        from app.services import type_inference
        prospect = Prospect(
            name=name,
            website=client_website,
            description=client_description,
            type=type_inference.infer_type(name=name, description=client_description or "", domain=client_website or ""),
        )
        db.add(prospect)
        db.flush()

    # Add this prospect to every remaining client's pipeline (if not already present)
    remaining_clients = db.query(Client).all()
    for cl in remaining_clients:
        existing = db.query(PipelineEntry).filter(
            PipelineEntry.client_id == cl.id,
            PipelineEntry.prospect_id == prospect.id,
        ).first()
        if not existing:
            db.add(PipelineEntry(
                client_id=cl.id,
                prospect_id=prospect.id,
                source=f"Auto-added after {name} demoted from client to prospect",
            ))

    db.commit()
    return {"status": "deleted", "name": name, "kept_as_prospect": True}


@router.delete("/{client_id}/cascade-everywhere")
def delete_client_and_company_everywhere(client_id: int, db: Session = Depends(get_db)):
    """
    Nuclear delete: remove the client AND wipe this company from the system entirely.
    Deletes: client record, matching prospect, all pipeline entries across all clients,
    business profile, behavior profile, relationships, intent signals.
    """
    from app.models import (CriterionScore, IntroPackage, ActivityLog as AL, IdentityFilter,
                            BusinessProfile, BehaviorProfile, IntentSignal)

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    name = client.name
    prospect = db.query(Prospect).filter(Prospect.name.ilike(name)).first()

    # 1. Wipe client-side data
    db.query(ScoringCriterion).filter(ScoringCriterion.client_id == client_id).delete(synchronize_session=False)
    db.query(IdentityFilter).filter(IdentityFilter.client_id == client_id).delete(synchronize_session=False)
    client_entry_ids = [e.id for e in db.query(PipelineEntry.id).filter(PipelineEntry.client_id == client_id).all()]
    if client_entry_ids:
        db.query(CriterionScore).filter(CriterionScore.pipeline_entry_id.in_(client_entry_ids)).delete(synchronize_session=False)
        db.query(IntroPackage).filter(IntroPackage.pipeline_entry_id.in_(client_entry_ids)).delete(synchronize_session=False)
        db.query(AL).filter(AL.pipeline_entry_id.in_(client_entry_ids)).delete(synchronize_session=False)
        db.query(PipelineEntry).filter(PipelineEntry.client_id == client_id).delete(synchronize_session=False)
    db.delete(client)

    # 2. Wipe prospect-side data (all pipelines referencing this company)
    if prospect:
        prospect_entry_ids = [e.id for e in db.query(PipelineEntry.id).filter(PipelineEntry.prospect_id == prospect.id).all()]
        if prospect_entry_ids:
            db.query(CriterionScore).filter(CriterionScore.pipeline_entry_id.in_(prospect_entry_ids)).delete(synchronize_session=False)
            db.query(IntroPackage).filter(IntroPackage.pipeline_entry_id.in_(prospect_entry_ids)).delete(synchronize_session=False)
            db.query(AL).filter(AL.pipeline_entry_id.in_(prospect_entry_ids)).delete(synchronize_session=False)
            db.query(PipelineEntry).filter(PipelineEntry.prospect_id == prospect.id).delete(synchronize_session=False)
        db.query(BusinessProfile).filter(BusinessProfile.prospect_id == prospect.id).delete(synchronize_session=False)
        db.query(BehaviorProfile).filter(BehaviorProfile.prospect_id == prospect.id).delete(synchronize_session=False)
        db.query(Relationship).filter(Relationship.prospect_id == prospect.id).delete(synchronize_session=False)
        db.query(IntentSignal).filter(IntentSignal.prospect_id == prospect.id).delete(synchronize_session=False)
        db.delete(prospect)

    db.commit()
    return {"status": "deleted_everywhere", "name": name}


# ---- Criteria Library ----

@router.get("/library/all")
def get_criteria_library(db: Session = Depends(get_db)):
    """Get the full criteria library grouped by category."""
    entries = db.query(CriteriaLibrary).order_by(CriteriaLibrary.group_order, CriteriaLibrary.sort_order).all()
    groups = {}
    for e in entries:
        if e.group_name not in groups:
            groups[e.group_name] = {"group_name": e.group_name, "group_order": e.group_order, "criteria": []}
        groups[e.group_name]["criteria"].append({
            "library_id": e.id,
            "name": e.name,
            "description": e.description,
            "why_it_matters": e.why_it_matters,
            "default_weight": e.default_weight,
        })
    return sorted(groups.values(), key=lambda g: g["group_order"])


@router.post("/{client_id}/criteria/toggle/{library_id}")
def toggle_criterion(client_id: int, library_id: int, db: Session = Depends(get_db)):
    """Toggle a library criterion on or off for a client."""
    lib = db.query(CriteriaLibrary).filter(CriteriaLibrary.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="Library criterion not found")

    # Check if this criterion already exists for this client
    existing = (
        db.query(ScoringCriterion)
        .filter(ScoringCriterion.client_id == client_id, ScoringCriterion.library_id == library_id)
        .first()
    )

    if existing:
        # Toggle active state
        existing.active = not existing.active
        db.commit()
        db.refresh(existing)
        return {"action": "toggled", "active": existing.active, "name": existing.name, "id": existing.id}
    else:
        # Create new criterion from library
        c = ScoringCriterion(
            client_id=client_id,
            library_id=library_id,
            name=lib.name,
            description=lib.description,
            why_it_matters=lib.why_it_matters,
            weight=lib.default_weight,
            sort_order=lib.sort_order,
            active=True,
            group_name=lib.group_name,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        return {"action": "created", "active": True, "name": c.name, "id": c.id}


# ---- Scoring Presets ----

# Each preset names library criteria and their override weights (1-10).
# Rationale embedded so the UI can explain the picks.
SCORING_PRESETS = {
    "carrier_to_tech_vendor": {
        "label": "Carrier → Tech Vendor",
        "description": "Evaluate tech vendors (insurtech, platforms, API providers) as partners for a carrier or MGA.",
        "criteria": {
            2: 8,   # Sells to the same customer type
            6: 8,   # Product Complementarity
            7: 7,   # API / Integration Readiness
            9: 5,   # Data & Analytics Capability
            14: 5,  # Partnership Track Record
            17: 6,  # Decision Maker Accessibility
        },
    },
    "carrier_to_carrier": {
        "label": "Carrier → Carrier Partnership",
        "description": "Evaluate other carriers for distribution partnerships, reinsurance, or co-marketing.",
        "criteria": {
            2: 7,   # Buyer Persona Match
            3: 7,   # Customer Segment Alignment
            1: 6,   # Geographic Overlap
            12: 8,  # Distribution Alignment
            15: 5,  # Competitive Position
            17: 5,  # Decision Maker Accessibility
        },
    },
    "agency_growth": {
        "label": "Agency Growth Targets",
        "description": "Evaluate carriers or MGAs for an independent agency building its appointment roster.",
        "criteria": {
            5: 8,   # SMB Commercial Focus
            1: 6,   # Geographic Overlap
            4: 5,   # Vertical Specialization
            11: 7,  # Lead Gen Compatibility
            18: 5,  # Sales Cycle Alignment
            20: 4,  # Conference & Event Proximity
        },
    },
    "distribution_expansion": {
        "label": "Distribution Expansion",
        "description": "Evaluate companies for adding new distribution channels (agency networks, MGAs, platforms).",
        "criteria": {
            12: 9,  # Distribution Alignment
            2: 7,   # Buyer Persona Match
            10: 6,  # Digital CX / Acquisition
            11: 7,  # Lead Gen Compatibility
            13: 5,  # Revenue Model Compatibility
            19: 5,  # Strategic Priority Fit
        },
    },
}


@router.get("/presets/list")
def list_scoring_presets():
    """Return the available scoring presets with metadata."""
    out = []
    for key, p in SCORING_PRESETS.items():
        out.append({
            "key": key,
            "label": p["label"],
            "description": p["description"],
            "criterion_count": len(p["criteria"]),
        })
    return out


@router.post("/{client_id}/presets/apply/{preset_key}")
def apply_scoring_preset(client_id: int, preset_key: str, db: Session = Depends(get_db)):
    """
    Apply a scoring preset: deactivates all current criteria, then enables
    the preset's criteria with their recommended weights.
    Pipeline rescoring is triggered separately by the frontend.
    """
    if preset_key == "custom":
        # Custom = clear everything. User builds from scratch.
        db.query(ScoringCriterion).filter(
            ScoringCriterion.client_id == client_id,
        ).update({"active": False}, synchronize_session=False)
        db.commit()
        return {"applied": "custom", "activated": 0, "deactivated": "all"}

    preset = SCORING_PRESETS.get(preset_key)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_key}' not found")

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # 1. Deactivate everything currently active
    db.query(ScoringCriterion).filter(
        ScoringCriterion.client_id == client_id,
    ).update({"active": False}, synchronize_session=False)

    # 2. For each criterion in the preset, upsert + activate with preset weight
    activated = 0
    for library_id, weight in preset["criteria"].items():
        lib = db.query(CriteriaLibrary).filter(CriteriaLibrary.id == library_id).first()
        if not lib:
            continue
        existing = (
            db.query(ScoringCriterion)
            .filter(ScoringCriterion.client_id == client_id, ScoringCriterion.library_id == library_id)
            .first()
        )
        if existing:
            existing.active = True
            existing.weight = weight
        else:
            db.add(ScoringCriterion(
                client_id=client_id,
                library_id=library_id,
                name=lib.name,
                description=lib.description,
                why_it_matters=lib.why_it_matters,
                weight=weight,
                sort_order=lib.sort_order,
                active=True,
                group_name=lib.group_name,
            ))
        activated += 1

    db.commit()
    return {
        "applied": preset_key,
        "label": preset["label"],
        "activated": activated,
        "deactivated": "all others",
    }


# ---- Scoring Criteria ----

@router.get("/{client_id}/criteria")
def list_criteria(client_id: int, include_inactive: bool = False, db: Session = Depends(get_db)):
    """List criteria for a client. By default only returns active criteria."""
    q = db.query(ScoringCriterion).filter(ScoringCriterion.client_id == client_id)
    if not include_inactive:
        q = q.filter(ScoringCriterion.active == True)
    criteria = q.order_by(ScoringCriterion.sort_order).all()
    return [
        {
            "id": c.id, "client_id": c.client_id, "name": c.name,
            "description": c.description, "why_it_matters": c.why_it_matters,
            "weight": c.weight, "sort_order": c.sort_order,
            "active": c.active if hasattr(c, 'active') and c.active is not None else True,
            "group_name": c.group_name if hasattr(c, 'group_name') else None,
            "library_id": c.library_id if hasattr(c, 'library_id') else None,
        }
        for c in criteria
    ]


@router.post("/{client_id}/criteria", response_model=CriterionOut)
def create_criterion(client_id: int, data: CriterionCreate, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    criterion = ScoringCriterion(client_id=client_id, **data.dict())
    db.add(criterion)
    db.commit()
    db.refresh(criterion)
    return criterion


@router.put("/{client_id}/criteria/{criterion_id}", response_model=CriterionOut)
def update_criterion(client_id: int, criterion_id: int, data: CriterionCreate, db: Session = Depends(get_db)):
    criterion = (
        db.query(ScoringCriterion)
        .filter(ScoringCriterion.id == criterion_id, ScoringCriterion.client_id == client_id)
        .first()
    )
    if not criterion:
        raise HTTPException(status_code=404, detail="Criterion not found")
    for key, val in data.dict(exclude_unset=True).items():
        setattr(criterion, key, val)
    db.commit()
    db.refresh(criterion)
    return criterion


@router.delete("/{client_id}/criteria/{criterion_id}")
def delete_criterion(client_id: int, criterion_id: int, db: Session = Depends(get_db)):
    criterion = (
        db.query(ScoringCriterion)
        .filter(ScoringCriterion.id == criterion_id, ScoringCriterion.client_id == client_id)
        .first()
    )
    if not criterion:
        raise HTTPException(status_code=404, detail="Criterion not found")
    db.delete(criterion)
    db.commit()
    return {"status": "deleted", "name": criterion.name}
