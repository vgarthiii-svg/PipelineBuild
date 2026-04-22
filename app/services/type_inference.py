"""
Type Inference Service - FREE

Determines company type from multiple free sources:
1. Apollo industry field (if configured, has domain)
2. HubSpot industry field (if configured)
3. Keyword matching on name + description

Used by client/prospect creation flows to auto-set accurate types.
"""

import re


# Maps external industry labels to our internal type values
INDUSTRY_TO_TYPE = {
    # Apollo/HubSpot common values
    "insurance": None,  # needs further classification
    "internet": "Technology",
    "computer software": "Technology",
    "information technology and services": "Technology",
    "information technology & services": "Technology",
    "software": "Technology",
    "saas": "Technology",
    "technology": "Technology",
    "computer & network security": "Technology",
    "financial services": None,  # needs further classification
    "banking": None,
    "venture capital": None,
    "internet marketplace platforms": "Marketplace",
    "online marketplace": "Marketplace",
    "marketplace": "Marketplace",
}


def infer_type(name: str, description: str = "", domain: str = "", employees: int = None) -> str:
    """
    Infer company type using free sources. Returns best-guess type or None.

    Order of operations:
    1. Try Apollo enrichment (by domain) - returns industry
    2. Try HubSpot search - returns industry
    3. Fall back to keyword matching on name + description

    Never calls Claude (no cost).
    """
    # Step 1: Try Apollo enrichment (free if key set)
    apollo_industry = _get_apollo_industry(name, domain)

    # Step 2: Try HubSpot (free if key set)
    hubspot_industry = _get_hubspot_industry(name)

    # Combine signals: use industry to narrow, then use keywords for specificity
    combined_text = " ".join([
        name or "",
        description or "",
        apollo_industry or "",
        hubspot_industry or "",
    ]).lower()

    # Step 3: Keyword-based classification
    return _classify_from_text(combined_text, employees)


def _get_apollo_industry(name: str, domain: str) -> str:
    """Get industry from Apollo enrichment (if configured)."""
    try:
        from app.services import apollo_enrich
        if not apollo_enrich.is_configured():
            return ""

        # Use stored domain or guess from name
        d = domain
        if not d:
            simple = "".join(c.lower() for c in (name or "") if c.isalnum())
            if simple:
                d = f"{simple}.com"

        if d:
            data = apollo_enrich.enrich_company(d)
            if data.get("status") == "ok":
                return data.get("industry", "") or ""
    except Exception as e:
        print(f"[TYPE_INFER] Apollo error: {e}")
    return ""


def _get_hubspot_industry(name: str) -> str:
    """Get industry from HubSpot (if configured)."""
    try:
        from app.services import hubspot_scan
        if not hubspot_scan.is_configured():
            return ""

        result = hubspot_scan.search_companies(name, limit=1)
        if result.get("available") and result.get("results"):
            return result["results"][0].get("industry", "") or ""
    except Exception as e:
        print(f"[TYPE_INFER] HubSpot error: {e}")
    return ""


def _classify_from_text(text: str, employees: int = None) -> str:
    """
    Classify company type from combined text using keyword matching.
    More specific matches win over generic ones.
    """
    text = text.lower()

    # Very specific keywords first
    if re.search(r"\bmga\b|managing general agent|managing general underwriter|\bmgu\b", text):
        return "MGA"

    if re.search(r"wholesale brok|surplus lines|e&s broker|excess.{1,20}surplus", text):
        return "Wholesale Broker"

    if re.search(r"marketplace|exchange platform|comparison shopping|lead marketplace", text):
        return "Marketplace"

    # Insurance-specific subtypes
    has_insurance = bool(re.search(r"insurance|insurer|carrier|underwrit|p&c|property.{1,10}casualty", text))
    has_specialty = bool(re.search(r"specialty|specialist|niche|non-standard", text))
    has_agency = bool(re.search(r"\bagency\b|agencies|indep.{1,10}agent", text))
    has_brokerage = bool(re.search(r"\bbrokerage\b|\bbroker\b", text))
    is_national = bool(re.search(r"national|nationwide|all 50 states|multi-state|coast.to.coast", text))
    is_regional = bool(re.search(r"regional|mutual|midwest|northeast|southeast|southwest|multi-state regional", text))

    # Technology indicators
    is_tech = bool(re.search(r"software|saas|platform|technology|insurtech|fintech|\bapi\b|cloud|digital.*platform|app-based|tech-enabled|ai-powered|machine learning", text))

    # Classification logic
    if has_insurance:
        if is_tech and not (has_agency or has_brokerage):
            return "Technology"  # InsurTech
        if has_specialty:
            return "Specialty Carrier"
        if has_brokerage:
            if is_national or (employees and employees > 5000):
                return "National Brokerage"
            return "National Brokerage"  # default for brokerages
        if has_agency:
            return "National Agency"
        # Pure insurance carrier
        if employees and employees > 10000:
            return "National Carrier"
        if is_national:
            return "National Carrier"
        return "Regional Carrier"  # default carrier

    # Not insurance-specific - check for tech/platform
    if is_tech:
        return "Technology"

    # Fallback: look at company name patterns
    if re.search(r"(agency|agencies)$", text):
        return "National Agency"
    if re.search(r"(brokerage)$", text):
        return "National Brokerage"
    if re.search(r"(partners|capital|holdings)$", text):
        # Likely PE / holding company - treat as tech/broker by default
        return "Technology"

    # Default: Technology (most insurtech-adjacent services)
    return "Technology"
