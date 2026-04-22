"""
HubSpot service.

Activates when HUBSPOT_API_KEY is set in .env.
Provides company search and contact lookup for the client selector and relationship scans.
"""

import os
import json
import urllib.request
import urllib.error


def _get_api_key():
    return os.environ.get("HUBSPOT_API_KEY", "").strip()


def is_configured():
    return bool(_get_api_key())


def search_companies(query: str, limit: int = 5) -> dict:
    """
    Search HubSpot companies by name.

    Returns:
        {
            "available": bool,
            "results": [
                {
                    "source": "hubspot",
                    "name": str,
                    "domain": str,
                    "description": str,
                    "phone": str,
                    "city": str,
                    "state": str,
                    "industry": str,
                    "employees": int or None,
                    "hubspot_id": str,
                }
            ]
        }
    """
    api_key = _get_api_key()
    if not api_key:
        return {"available": False, "results": []}

    try:
        url = "https://api.hubapi.com/crm/v3/objects/companies/search"
        payload = json.dumps({
            "query": query,
            "properties": [
                "name", "domain", "description", "phone",
                "city", "state", "industry", "numberofemployees"
            ],
            "limit": limit,
        }).encode()

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        results = []
        for r in data.get("results", []):
            props = r.get("properties", {})
            emp = props.get("numberofemployees")
            results.append({
                "source": "hubspot",
                "name": props.get("name", ""),
                "domain": props.get("domain", ""),
                "description": props.get("description", ""),
                "phone": props.get("phone", ""),
                "city": props.get("city", ""),
                "state": props.get("state", ""),
                "industry": props.get("industry", ""),
                "employees": int(emp) if emp else None,
                "hubspot_id": r.get("id", ""),
            })

        return {"available": True, "results": results}

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, Exception) as e:
        print(f"[HUBSPOT] Search error: {e}")
        return {"available": False, "results": []}


def get_company_contacts(company_id: str) -> list:
    """Get contacts associated with a HubSpot company."""
    api_key = _get_api_key()
    if not api_key or not company_id:
        return []

    try:
        url = f"https://api.hubapi.com/crm/v3/objects/companies/{company_id}/associations/contacts"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {api_key}")

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        contact_ids = [r.get("id") for r in data.get("results", []) if r.get("id")]
        contacts = []

        for cid in contact_ids[:5]:
            curl = f"https://api.hubapi.com/crm/v3/objects/contacts/{cid}?properties=firstname,lastname,jobtitle,email"
            creq = urllib.request.Request(curl)
            creq.add_header("Authorization", f"Bearer {api_key}")
            with urllib.request.urlopen(creq, timeout=10) as cresp:
                cdata = json.loads(cresp.read())
                props = cdata.get("properties", {})
                contacts.append({
                    "name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
                    "title": props.get("jobtitle", ""),
                    "email": props.get("email", ""),
                })

        return contacts

    except Exception as e:
        print(f"[HUBSPOT] Contact lookup error: {e}")
        return []


def list_recently_modified_companies(days: int = 7, limit: int = 200) -> dict:
    """
    Return HubSpot companies whose `hs_lastmodifieddate` falls within the last `days`.
    Used by the nightly HubSpot sync agent.

    Returns the same shape as search_companies() so callers can reuse handling.
    """
    api_key = _get_api_key()
    if not api_key:
        return {"available": False, "results": []}

    try:
        import datetime as _dt
        cutoff_ms = int((_dt.datetime.utcnow() - _dt.timedelta(days=days)).timestamp() * 1000)

        url = "https://api.hubapi.com/crm/v3/objects/companies/search"
        payload = json.dumps({
            "filterGroups": [{
                "filters": [{
                    "propertyName": "hs_lastmodifieddate",
                    "operator": "GTE",
                    "value": str(cutoff_ms),
                }],
            }],
            "sorts": [{"propertyName": "hs_lastmodifieddate", "direction": "DESCENDING"}],
            "properties": [
                "name", "domain", "description", "phone",
                "city", "state", "industry", "numberofemployees",
                "hs_lastmodifieddate",
            ],
            "limit": min(limit, 100),  # HubSpot cap per page is 100
        }).encode()

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        results = []
        for r in data.get("results", []):
            props = r.get("properties", {})
            emp = props.get("numberofemployees")
            results.append({
                "source": "hubspot",
                "name": props.get("name", ""),
                "domain": props.get("domain", ""),
                "description": props.get("description", ""),
                "phone": props.get("phone", ""),
                "city": props.get("city", ""),
                "state": props.get("state", ""),
                "industry": props.get("industry", ""),
                "employees": int(emp) if emp else None,
                "hubspot_id": r.get("id", ""),
                "last_modified": props.get("hs_lastmodifieddate"),
            })
        return {"available": True, "results": results, "total": data.get("total", len(results))}
    except Exception as e:
        print(f"[HUBSPOT] Recent-modified lookup error: {e}")
        return {"available": False, "results": [], "error": str(e)}


def list_companies_in_list(list_id: str, limit: int = 200) -> dict:
    """
    Return the companies that are members of a specific HubSpot list.
    Uses the v3 Lists API: first get membership record IDs, then batch-read properties.

    Returns the same shape as list_recently_modified_companies() for drop-in use.
    """
    api_key = _get_api_key()
    if not api_key:
        return {"available": False, "results": []}
    if not list_id:
        return {"available": False, "results": [], "error": "No list_id configured"}

    try:
        # Step 1: get memberships (company IDs in the list)
        mem_url = f"https://api.hubapi.com/crm/v3/lists/{list_id}/memberships?limit={min(limit, 250)}"
        mem_req = urllib.request.Request(mem_url)
        mem_req.add_header("Authorization", f"Bearer {api_key}")
        with urllib.request.urlopen(mem_req, timeout=15) as resp:
            mem_data = json.loads(resp.read())
        record_ids = [r.get("recordId") for r in mem_data.get("results", []) if r.get("recordId")]

        if not record_ids:
            return {"available": True, "results": [], "total": 0}

        # Step 2: batch-read company properties (up to 100 per batch)
        results = []
        for i in range(0, len(record_ids), 100):
            batch_ids = record_ids[i:i + 100]
            batch_url = "https://api.hubapi.com/crm/v3/objects/companies/batch/read"
            payload = json.dumps({
                "inputs": [{"id": rid} for rid in batch_ids],
                "properties": [
                    "name", "domain", "description", "phone",
                    "city", "state", "industry", "numberofemployees",
                    "hs_lastmodifieddate",
                ],
            }).encode()
            breq = urllib.request.Request(batch_url, data=payload, method="POST")
            breq.add_header("Authorization", f"Bearer {api_key}")
            breq.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(breq, timeout=15) as bresp:
                bdata = json.loads(bresp.read())
            for r in bdata.get("results", []):
                props = r.get("properties", {})
                emp = props.get("numberofemployees")
                results.append({
                    "source": "hubspot",
                    "name": props.get("name", ""),
                    "domain": props.get("domain", ""),
                    "description": props.get("description", ""),
                    "phone": props.get("phone", ""),
                    "city": props.get("city", ""),
                    "state": props.get("state", ""),
                    "industry": props.get("industry", ""),
                    "employees": int(emp) if emp else None,
                    "hubspot_id": r.get("id", ""),
                    "last_modified": props.get("hs_lastmodifieddate"),
                })
        return {"available": True, "results": results, "total": len(results)}
    except Exception as e:
        print(f"[HUBSPOT] list_companies_in_list error: {e}")
        return {"available": False, "results": [], "error": str(e)}


def scan_hubspot(prospect_name: str):
    """
    Scan HubSpot CRM for existing contacts and company records.
    Used by the relationship scan.
    """
    result = search_companies(prospect_name, limit=3)
    if not result["available"] or not result["results"]:
        return {"hits": 0, "details": [], "status": "no_results" if result["available"] else "not_configured"}

    details = []
    for company in result["results"]:
        contacts = get_company_contacts(company.get("hubspot_id", ""))
        for c in contacts:
            details.append({
                "contact_id": company.get("hubspot_id"),
                "name": c["name"],
                "title": c["title"],
                "email": c["email"],
            })

    return {
        "hits": len(details),
        "details": details,
        "status": "ok",
    }
