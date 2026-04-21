"""
Apollo.io enrichment service stub.

Activates when APOLLO_API_KEY is set in .env.
Enriches company data: description, revenue, employees, HQ, industry.
"""


def enrich_company(domain: str):
    """
    Enrich a company using Apollo's organization enrichment API.

    Returns:
        dict with company data or None if not configured.
    """
    # TODO: Implement when Apollo API key is configured
    # Uses: Bulk org enrichment (up to 10 per call, works on free plan)
    # Returns: description, revenue, employee count, HQ, industry, LinkedIn
    return {
        "status": "not_configured",
        "message": "Apollo API key not configured. Add APOLLO_API_KEY to .env to enable.",
    }
