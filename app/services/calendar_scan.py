"""
Google Calendar scan service stub.

Activates when Google Calendar OAuth credentials are configured.
Searches for past meetings and shared event attendance.
"""


def scan_calendar(prospect_name: str):
    """
    Scan Google Calendar for meeting history with a prospect company.

    Returns:
        dict with keys: hits (int), details (list of dicts)
        Each detail: {event_name, date, attendees}
    """
    # TODO: Implement when Calendar OAuth is configured
    # Search events: fullText="{company name}" over last 2 years
    # Check attendee lists for prospect domain matches
    return {
        "hits": 0,
        "details": [],
        "status": "not_configured",
        "message": "Google Calendar OAuth not configured. Add credentials to .env to enable.",
    }
