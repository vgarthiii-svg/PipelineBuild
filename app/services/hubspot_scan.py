"""
HubSpot scan service stub.

Activates when HUBSPOT_API_KEY is set in .env.
Searches for contacts and companies matching the prospect.
"""


def scan_hubspot(prospect_name: str):
    """
    Scan HubSpot CRM for existing contacts and company records.

    Returns:
        dict with keys: hits (int), details (list of dicts)
        Each detail: {contact_id, name, title, email, last_activity}
    """
    # TODO: Implement when HubSpot API key is configured
    # Search contacts: query="{company name}"
    # Search companies: query="{company name}"
    return {
        "hits": 0,
        "details": [],
        "status": "not_configured",
        "message": "HubSpot API key not configured. Add HUBSPOT_API_KEY to .env to enable.",
    }
