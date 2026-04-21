"""
Claude API integration for the BD Pipeline Agent.

Handles:
- Company profiling
- Automated scoring with reasoning
- Intro email generation in Vinnie's voice
- Email thread parsing
- Relationship evidence assessment
"""

import json
import os
from typing import Optional


def _get_client():
    """Get Anthropic client. Returns None if key not set."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        print("[CLAUDE] anthropic package not installed")
        return None


def profile_company(company_name: str) -> Optional[dict]:
    """Research a company and produce a structured profile."""
    client = _get_client()
    if not client:
        return None

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system="You are a B2B business development analyst. Research the following company and produce a structured profile. Return valid JSON only.",
        messages=[{
            "role": "user",
            "content": f"""Profile {company_name}. I need:
- What they sell (products/services)
- Who they sell to (target buyer, segment)
- How they go to market (channels, sales motion)
- Problems they solve (3 key pain points)
- Their value chain position (upstream and downstream needs)
- 3-5 competitors and how they differ

Return as JSON with keys: products, target_buyer, go_to_market, problems_solved, value_chain_upstream, value_chain_downstream, competitors"""
        }],
    )

    try:
        text = response.content[0].text
        # Try to extract JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        return {"raw_response": response.content[0].text}


def score_prospect(
    prospect_name: str,
    prospect_description: str,
    client_name: str,
    client_description: str,
    criteria: list,
) -> Optional[list]:
    """
    Score a prospect against client criteria.

    Args:
        criteria: List of dicts with keys: id, name, description, weight
    Returns:
        List of dicts: [{criterion_id, score, reasoning}]
    """
    client = _get_client()
    if not client:
        return None

    criteria_text = "\n".join([
        f"- {c['name']} (weight: {c['weight']}/10): {c['description']}"
        for c in criteria
    ])

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system="You are scoring prospect companies for product-market fit with a specific client. Return valid JSON only.",
        messages=[{
            "role": "user",
            "content": f"""Score {prospect_name} against these criteria for {client_name}:

{criteria_text}

Client: {client_name} - {client_description}
Prospect: {prospect_name} - {prospect_description}

For each criterion, provide a score (0-5) and a one-sentence reasoning.
Return JSON array: [{{"criterion_name": "...", "score": N, "reasoning": "..."}}]"""
        }],
    )

    try:
        text = response.content[0].text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        return None


def generate_intro_package(
    prospect_name: str,
    prospect_description: str,
    client_name: str,
    client_description: str,
    client_key_stat: str,
    contact_name: str,
    contact_title: str,
    relationship_context: str,
    fit_reasoning: str,
) -> dict:
    """Generate a full intro package including email, talking points, and value prop."""
    client = _get_client()
    if not client:
        return {}

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system="""You are writing a business introduction email and supporting materials.
The sender (Vinnie) is introducing his client's product/service to a prospect company.
Write in Vinnie's voice: direct, conversational, confident, no corporate jargon.
No em dashes. No buzzwords (passionate, leveraged, architected, seamless, scalable, dynamic).
Short paragraphs. Include a specific stat about the client. End with a clear ask.
Return valid JSON only.""",
        messages=[{
            "role": "user",
            "content": f"""Write an introduction package.

From: Vinnie Garth
To: {contact_name}, {contact_title} at {prospect_name}
Introducing: {client_name} ({client_description})
Key stat: {client_key_stat}
Relationship context: {relationship_context}
Why this is a fit: {fit_reasoning}
Prospect info: {prospect_description}

Return JSON with:
- email_subject: string
- email_body: string (word-for-word, ready to send, 3-4 short paragraphs)
- talking_points: array of 3 strings (each tied to a specific pain point)
- value_prop_prospect: string (why this helps the prospect)
- value_prop_client: string (why this helps the client)
- mutual_connections: array of strings
- objections: array of {{"objection": "...", "response": "..."}} (2-3 items)"""
        }],
    )

    try:
        text = response.content[0].text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        return {"email_body": response.content[0].text, "email_subject": f"Quick intro: {client_name} x {prospect_name}"}


def parse_email_for_companies(email_content: str) -> Optional[list]:
    """Extract company names from an email thread."""
    client = _get_client()
    if not client:
        return None

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system="Extract company names from this email thread. The sender is asking the recipient to make introductions to specific companies. Return ONLY a JSON array of company name strings. Do not include the sender's company or the recipient's company.",
        messages=[{"role": "user", "content": email_content}],
    )

    try:
        text = response.content[0].text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        return None


def assess_relationship_evidence(
    prospect_name: str,
    gmail_results: str,
    hubspot_results: str,
    calendar_results: str,
    conference_results: str,
    relmap_results: str,
) -> Optional[dict]:
    """Assess relationship evidence and assign an RS score."""
    client = _get_client()
    if not client:
        return None

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system="""Based on evidence from five data sources, assign a relationship strength score (0-5) and explain your reasoning.

Scale:
5 = Inner Circle (former employer, active business partner)
4 = Strong (multiple email threads, past meetings)
3 = Warm (conference meeting, occasional emails)
2 = Light (one email, LinkedIn connection, one-hop intro)
1 = Aware (name in event list, CRM record, no direct contact)
0 = Cold (zero evidence)

Return valid JSON only.""",
        messages=[{
            "role": "user",
            "content": f"""Evidence for {prospect_name}:
Gmail: {gmail_results}
HubSpot: {hubspot_results}
Calendar: {calendar_results}
Conference: {conference_results}
Relationship Map: {relmap_results}

Return JSON: {{"score": N, "reasoning": "...", "best_contact": "...", "warmest_path": "..."}}"""
        }],
    )

    try:
        text = response.content[0].text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        return None
