"""
Apollo.io service.

Activates when APOLLO_API_KEY is set in .env.
Provides org enrichment (free plan). Search requires paid plan.
"""

import os
import json
import urllib.request
import urllib.error


def _get_api_key():
    return os.environ.get("APOLLO_API_KEY", "").strip()


def is_configured():
    return bool(_get_api_key())


def _auth_headers():
    """Apollo requires X-Api-Key header + real User-Agent (Cloudflare blocks bots)."""
    return {
        "Content-Type": "application/json",
        "X-Api-Key": _get_api_key(),
        "Cache-Control": "no-cache",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }


def search_organizations(query: str, limit: int = 5) -> dict:
    """
    Search Apollo organizations by name. NOT AVAILABLE ON FREE PLAN.
    Returns empty results on free plan - use enrich_company() instead.
    """
    api_key = _get_api_key()
    if not api_key:
        return {"available": False, "results": []}

    # Free plan doesn't include search - just return empty
    # If the user upgrades later, this can try the search endpoint
    return {
        "available": False,
        "results": [],
        "note": "Apollo search requires paid plan. Enrichment by domain is used instead."
    }


def enrich_company(domain: str) -> dict:
    """
    Enrich a company using Apollo's organization enrichment API.
    Available on free plan. Returns firmographic data (revenue, employees, HQ, etc.)
    """
    api_key = _get_api_key()
    if not api_key or not domain:
        return {"status": "not_configured"}

    # Strip protocol/path from domain
    domain = domain.lower().replace("https://", "").replace("http://", "").split("/")[0].strip()
    if not domain:
        return {"status": "invalid_domain"}

    try:
        url = f"https://api.apollo.io/api/v1/organizations/enrich?domain={domain}"
        req = urllib.request.Request(url, method="GET")
        for k, v in _auth_headers().items():
            req.add_header(k, v)

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        org = data.get("organization") or {}
        if not org:
            return {"status": "not_found"}

        return {
            "status": "ok",
            "name": org.get("name", ""),
            "domain": org.get("primary_domain", "") or org.get("website_url", ""),
            "description": org.get("short_description", "") or org.get("seo_description", ""),
            "revenue": org.get("estimated_annual_revenue", "") or org.get("annual_revenue_printed", ""),
            "employees": org.get("estimated_num_employees"),
            "city": org.get("city", ""),
            "state": org.get("state", ""),
            "country": org.get("country", ""),
            "industry": org.get("industry", ""),
            "linkedin_url": org.get("linkedin_url", ""),
            "phone": org.get("phone", ""),
            "founded_year": org.get("founded_year"),
            "technologies": [t.get("name") for t in (org.get("current_technologies") or []) if t.get("name")],
        }

    except urllib.error.HTTPError as e:
        if e.code == 403:
            return {"status": "forbidden", "message": "Apollo endpoint not accessible with this API key"}
        return {"status": "error", "code": e.code, "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def bulk_enrich_companies(domains: list) -> dict:
    """
    Bulk enrich up to 10 companies at a time. Free on Apollo's free plan.
    Returns {domain: org_data} mapping.
    """
    api_key = _get_api_key()
    if not api_key:
        return {}

    # Clean domains
    clean_domains = []
    for d in domains[:10]:  # Apollo caps at 10 per call
        if d:
            dd = d.lower().replace("https://", "").replace("http://", "").split("/")[0].strip()
            if dd:
                clean_domains.append(dd)

    if not clean_domains:
        return {}

    try:
        url = "https://api.apollo.io/api/v1/organizations/bulk_enrich"
        payload = json.dumps({"domains": clean_domains}).encode()
        req = urllib.request.Request(url, data=payload, method="POST")
        for k, v in _auth_headers().items():
            req.add_header(k, v)

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        results = {}
        for org in data.get("organizations", []):
            domain = org.get("primary_domain") or org.get("website_url", "")
            if domain:
                results[domain] = {
                    "status": "ok",
                    "name": org.get("name", ""),
                    "domain": domain,
                    "description": org.get("short_description", "") or org.get("seo_description", ""),
                    "revenue": org.get("estimated_annual_revenue", ""),
                    "employees": org.get("estimated_num_employees"),
                    "city": org.get("city", ""),
                    "state": org.get("state", ""),
                    "industry": org.get("industry", ""),
                    "linkedin_url": org.get("linkedin_url", ""),
                    "phone": org.get("phone", ""),
                    "founded_year": org.get("founded_year"),
                }
        return results

    except Exception as e:
        print(f"[APOLLO] Bulk enrich error: {e}")
        return {}
