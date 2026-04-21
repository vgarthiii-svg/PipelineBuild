"""
Gmail scan service stub.

Activates when Gmail OAuth credentials are configured.
Searches for email threads with prospect company domains and names.
"""


def scan_gmail(prospect_name: str, prospect_domain: str = None, alternate_domains: list = None):
    """
    Scan Gmail for email history with a prospect company.

    Returns:
        dict with keys: hits (int), details (list of dicts)
        Each detail: {contact, subject, date, snippet, thread_nature}
    """
    # TODO: Implement when Gmail OAuth is configured
    # Search patterns:
    #   from:@{domain} OR to:@{domain}
    #   "{company name}" (broader text search)
    # Filter out: noreply@, password resets, marketing, system notifications
    return {
        "hits": 0,
        "details": [],
        "status": "not_configured",
        "message": "Gmail OAuth not configured. Add credentials to .env to enable.",
    }
