"""
Business Profile Generation Service

3-layer generation strategy:
  Layer 1 (FREE): Heuristic profile from name/type/domain. Always runs.
  Layer 2 (FREE if keys set): Apollo + HubSpot firmographic enrichment.
  Layer 3 (COST-GATED): Claude deep research profile.
"""

import json
import os
from datetime import datetime, timedelta


# ============ LAYER 1: HEURISTIC (FREE, INSTANT) ============

TYPE_PROFILE_MAP = {
    "Regional Carrier": {
        "one_liner": "Regional property and casualty insurance carrier",
        "target_customer_types": ["Independent agents", "Brokers", "Commercial businesses"],
        "target_segments": ["SMB", "mid-market"],
        "target_verticals": ["P&C Insurance"],
        "sales_channels": ["Independent agent network", "Direct"],
        "market_position": "challenger",
    },
    "National Carrier": {
        "one_liner": "National property and casualty insurance carrier with broad market presence",
        "target_customer_types": ["Agents", "Brokers", "Direct consumers", "Commercial businesses"],
        "target_segments": ["SMB", "mid-market", "enterprise"],
        "target_verticals": ["P&C Insurance"],
        "sales_channels": ["Captive agents", "Independent agents", "Direct"],
        "market_position": "leader",
    },
    "Specialty Carrier": {
        "one_liner": "Specialty insurance carrier focused on niche commercial lines",
        "target_customer_types": ["Wholesale brokers", "Specialty agencies"],
        "target_segments": ["SMB", "mid-market"],
        "target_verticals": ["P&C Insurance", "Specialty Insurance"],
        "sales_channels": ["Wholesale", "Specialty agents"],
        "market_position": "niche",
    },
    "National Brokerage": {
        "one_liner": "National insurance brokerage providing commercial risk management",
        "target_customer_types": ["Mid-market and enterprise businesses"],
        "target_segments": ["mid-market", "enterprise"],
        "target_verticals": ["P&C Insurance", "Benefits"],
        "sales_channels": ["Direct", "Producer network"],
        "market_position": "leader",
    },
    "National Agency": {
        "one_liner": "National insurance agency with franchise or captive distribution model",
        "target_customer_types": ["Consumers", "Small businesses"],
        "target_segments": ["SMB"],
        "target_verticals": ["P&C Insurance"],
        "sales_channels": ["Franchise agents", "Captive producers"],
        "market_position": "challenger",
    },
    "Wholesale Broker": {
        "one_liner": "Wholesale insurance broker placing specialty and hard-to-place risks",
        "target_customer_types": ["Retail agents", "Brokers"],
        "target_segments": ["mid-market", "enterprise"],
        "target_verticals": ["Specialty Insurance", "Excess and Surplus"],
        "sales_channels": ["Wholesale"],
        "market_position": "niche",
    },
    "Technology": {
        "one_liner": "Technology vendor providing software or platform solutions for insurance",
        "target_customer_types": ["Carriers", "Agencies", "MGAs", "Brokers"],
        "target_segments": ["mid-market", "enterprise"],
        "target_verticals": ["InsurTech"],
        "sales_channels": ["Direct sales", "Channel partners"],
        "market_position": "challenger",
    },
    "Marketplace": {
        "one_liner": "Digital marketplace or exchange connecting insurance buyers and sellers",
        "target_customer_types": ["SMBs", "Consumers", "Carriers"],
        "target_segments": ["SMB"],
        "target_verticals": ["InsurTech"],
        "sales_channels": ["Digital", "Partner network"],
        "market_position": "challenger",
    },
    "MGA": {
        "one_liner": "Managing General Agent with underwriting authority for specific carriers",
        "target_customer_types": ["Retail agents", "Brokers"],
        "target_segments": ["SMB", "mid-market"],
        "target_verticals": ["P&C Insurance", "Specialty Insurance"],
        "sales_channels": ["Wholesale", "Agent network"],
        "market_position": "niche",
    },
}


def generate_heuristic_profile(prospect) -> dict:
    """
    Layer 1: Generate a basic business profile from prospect metadata.
    Always free. Runs on every new company.
    Returns a dict that maps directly to BusinessProfile columns.
    """
    profile = {
        "generated_by": "heuristic",
        "generation_depth": "basic",
        "confidence_score": 25,
        "last_refreshed": datetime.utcnow(),
        "refresh_due": datetime.utcnow() + timedelta(days=90),
    }

    # Look up type-based defaults
    type_data = TYPE_PROFILE_MAP.get(prospect.type, {})
    if type_data:
        profile["one_liner"] = type_data.get("one_liner")
        profile["target_customer_types"] = json.dumps(type_data.get("target_customer_types", []))
        profile["target_segments"] = json.dumps(type_data.get("target_segments", []))
        profile["target_verticals"] = json.dumps(type_data.get("target_verticals", []))
        profile["sales_channels"] = json.dumps(type_data.get("sales_channels", []))
        profile["market_position"] = type_data.get("market_position")
        profile["confidence_score"] = 35
    else:
        profile["one_liner"] = f"{prospect.name} - business profile not yet enriched"

    # Use existing prospect data if available
    if prospect.description:
        profile["long_description"] = prospect.description
        profile["confidence_score"] = min(100, profile["confidence_score"] + 10)

    if prospect.hq_city or prospect.hq_state:
        hq_parts = [prospect.hq_city, prospect.hq_state]
        profile["headquarters"] = ", ".join([p for p in hq_parts if p])

    # Infer pricing model from type
    if prospect.type in ("Technology", "Marketplace"):
        profile["pricing_model"] = "SaaS or usage-based"
    elif prospect.type and "Carrier" in prospect.type:
        profile["pricing_model"] = "Premium-based"
    elif prospect.type and "Brokerage" in prospect.type:
        profile["pricing_model"] = "Commission-based"

    return profile


# ============ LAYER 2: ENRICHMENT (FREE if API keys) ============

def enrich_profile(prospect, existing_profile=None) -> dict:
    """
    Layer 2: Enrich profile using Apollo and HubSpot.
    Free if APOLLO_API_KEY or HUBSPOT_API_KEY is set. Returns partial update dict.
    """
    updates = {}
    enriched = False

    # Try Apollo first for firmographics
    from app.services import apollo_enrich, hubspot_scan

    if apollo_enrich.is_configured():
        # Apollo needs a domain. Use stored domain, or guess from company name.
        domain = prospect.domain
        if not domain:
            # Simple heuristic: "Sentry" -> "sentry.com", "Amtrust" -> "amtrust.com"
            simple_name = "".join(c.lower() for c in prospect.name if c.isalnum())
            if simple_name:
                domain = f"{simple_name}.com"

        if domain:
            try:
                apollo_data = apollo_enrich.enrich_company(domain)
                if apollo_data.get("status") == "ok":
                    if apollo_data.get("description"):
                        updates["long_description"] = apollo_data["description"]
                    if apollo_data.get("city") or apollo_data.get("state"):
                        hq = ", ".join([x for x in [apollo_data.get("city"), apollo_data.get("state")] if x])
                        if hq:
                            updates["headquarters"] = hq
                    if apollo_data.get("founded_year"):
                        updates["founded_year"] = apollo_data["founded_year"]
                    # Store the discovered domain back on the prospect
                    if not prospect.domain and apollo_data.get("domain"):
                        prospect.domain = apollo_data["domain"]
                    # Store employees/revenue on prospect
                    if apollo_data.get("employees") and not prospect.employees:
                        prospect.employees = apollo_data["employees"]
                    if apollo_data.get("revenue") and not prospect.revenue:
                        prospect.revenue = apollo_data["revenue"]
                    enriched = True
            except Exception as e:
                print(f"[PROFILE] Apollo enrichment error for {prospect.name}: {e}")

    # Try HubSpot for contacts and description
    if hubspot_scan.is_configured():
        try:
            hs_result = hubspot_scan.search_companies(prospect.name, limit=1)
            if hs_result.get("available") and hs_result.get("results"):
                hs_data = hs_result["results"][0]
                if not updates.get("long_description") and hs_data.get("description"):
                    updates["long_description"] = hs_data["description"]
                if not updates.get("headquarters") and (hs_data.get("city") or hs_data.get("state")):
                    hq = ", ".join([x for x in [hs_data.get("city"), hs_data.get("state")] if x])
                    if hq:
                        updates["headquarters"] = hq
                enriched = True
        except Exception as e:
            print(f"[PROFILE] HubSpot enrichment error: {e}")

    if enriched:
        updates["generated_by"] = "enrichment"
        updates["generation_depth"] = "enriched"
        updates["confidence_score"] = 65
        updates["last_refreshed"] = datetime.utcnow()
        updates["refresh_due"] = datetime.utcnow() + timedelta(days=90)

    return updates


# ============ LAYER 3: DEEP RESEARCH (COST-GATED) ============

def deep_research_profile(prospect, existing_profile=None) -> dict:
    """
    Layer 3: Full Claude deep research. COST-GATED - only called after user approval.
    Returns a profile dict with all fields populated.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "Claude API key not configured"}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        context = f"{prospect.name}"
        if prospect.domain:
            context += f" ({prospect.domain})"
        if prospect.description:
            context += f" - {prospect.description}"

        resp = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=3000,
            system="You are a B2B business intelligence analyst. Research this company and produce a comprehensive business profile. Return valid JSON only.",
            messages=[{
                "role": "user",
                "content": f"""Research {context} and return JSON with these exact keys:
- one_liner: Single sentence describing what they do
- long_description: 3-4 sentence description
- founded_year: integer or null
- headquarters: "City, State" or null
- primary_products: array of their main products
- secondary_products: array of supplementary products
- flagship_product: their lead/most important product
- target_customer_types: array of customer types they sell to
- target_segments: array from ["SMB", "mid-market", "enterprise"]
- target_verticals: array of industries served
- geographic_markets: array of regions (e.g., "NAM", "EMEA")
- sales_channels: array from ["direct", "partner", "marketplace", "captive agents", "independent agents"]
- pricing_model: "SaaS", "transactional", "per-policy", "commission", etc.
- typical_deal_size: "$10k-$50k" etc. or null
- value_chain_upstream: array of what THEY need from suppliers/vendors
- value_chain_downstream: array of what their CUSTOMERS need after buying from them
- key_integrations: array of platforms they integrate with (Guidewire, Salesforce, etc.)
- main_competitors: array of objects [{{"name": "...", "differentiator": "..."}}]
- key_differentiators: what sets them apart
- market_position: "leader", "challenger", or "niche"
- recent_developments: array of recent news/announcements
- growth_indicators: 1-2 sentences on hiring/expansion/funding"""
            }],
        )

        text = resp.content[0].text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        data = json.loads(text.strip())

        # Convert arrays to JSON strings for storage
        for key in ["primary_products", "secondary_products", "target_customer_types",
                    "target_segments", "target_verticals", "geographic_markets",
                    "sales_channels", "value_chain_upstream", "value_chain_downstream",
                    "key_integrations", "main_competitors", "recent_developments"]:
            if key in data and isinstance(data[key], list):
                data[key] = json.dumps(data[key])

        data["generated_by"] = "claude"
        data["generation_depth"] = "deep"
        data["confidence_score"] = 90
        data["last_refreshed"] = datetime.utcnow()
        data["refresh_due"] = datetime.utcnow() + timedelta(days=90)

        return data

    except Exception as e:
        print(f"[PROFILE] Claude deep research error: {e}")
        return {"error": str(e)}


# ============ ORCHESTRATION ============

def upsert_profile(prospect, db, run_enrichment=True):
    """
    Generate or update a profile for a prospect.
    Always runs Layer 1 (free heuristic).
    Optionally runs Layer 2 (enrichment) if run_enrichment=True and keys are set.
    Never runs Layer 3 (deep research) - that requires explicit user approval.
    """
    from app.models import BusinessProfile

    profile = db.query(BusinessProfile).filter(BusinessProfile.prospect_id == prospect.id).first()

    # Layer 1: Heuristic
    heuristic_data = generate_heuristic_profile(prospect)

    if not profile:
        profile = BusinessProfile(prospect_id=prospect.id, **heuristic_data)
        db.add(profile)
    else:
        # Only upgrade if current depth is basic or lower
        if profile.generation_depth in ("basic", None):
            for key, val in heuristic_data.items():
                setattr(profile, key, val)

    db.flush()

    # Layer 2: Enrichment
    if run_enrichment:
        enrichment_data = enrich_profile(prospect, profile)
        if enrichment_data and not enrichment_data.get("error"):
            for key, val in enrichment_data.items():
                setattr(profile, key, val)
            db.flush()

    return profile
