"""
Importers that load enriched prospect sheets into the pipeline database.

This is the bridge between the document layer (CSV/markdown produced by the
Claude agent) and the web app's database. Given a client and a scored CSV,
it creates prospects, relationships (contacts), and scored pipeline entries so
the data shows up in the dashboard.

Design notes:
- Contacts are stored as Relationship rows (the dashboard's "Best Contact"
  column reads from there), so no schema change is needed.
- The per-account "signal" (e.g. "chose Guidewire") goes into the pipeline
  entry's notes field.
- Prospecting lists are scored fit-led (default 80/20 PMF/RS weighting) because
  most direct-sales targets are cold; warm ties still get elevated via RS.
- Everything is idempotent: re-running updates in place instead of duplicating.
"""

import csv
import json
import os
from datetime import date, datetime

from app.models import (
    Client, ScoringCriterion, Prospect, PipelineEntry, Relationship, ActivityLog,
)
from app.scoring import calculate_pmf, calculate_matchmaker, assign_tier

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))


# ---- column auto-detection ----

_COLS = {
    "name":   ["Company", "Partner Name", "name"],
    "type":   ["Segment", "Partner Type", "type"],
    "hq":     ["HQ", "hq"],
    "fit":    ["Fit (re-scored)", "Fit (1-5)", "Fit", "fit"],
    "contact": ["Contact (enriched)", "Contact", "contact"],
    "signal": ["Signal (enriched)", "Signal", "signal", "Trigger — Why Now"],
    "accelerant": ["Outreach accelerant", "accelerant"],
    "desc":   ["Primary Lines of Business", "description"],
}


def _pick(fieldnames, keys):
    for k in keys:
        if k in fieldnames:
            return k
    return None


def _colmap(fieldnames):
    return {role: _pick(fieldnames, cands) for role, cands in _COLS.items()}


# ---- parsers ----

def _parse_hq(hq):
    """'Buffalo, NY' -> ('Buffalo', 'NY'). Returns (city, state)."""
    if not hq:
        return None, None
    hq = hq.strip()
    if "," in hq:
        city, _, rest = hq.partition(",")
        state = rest.strip().split("/")[0].strip()[:24]
        return city.strip() or None, state or None
    return hq or None, None


def _parse_contact(s):
    """'Stephen Cross, VP & CIO' -> ('Stephen Cross', 'VP & CIO'). No name -> (None, s)."""
    if not s:
        return None, None
    s = s.strip()
    lowered = s.lower()
    # Rows that describe absence of a public contact
    no_name_markers = ("no public", "no named", "name tbd", "role open", "not public")
    if "," in s:
        name, _, title = s.partition(",")
        name, title = name.strip(), title.strip()
        # If the "name" is actually a description like "No public CIO"
        if any(m in name.lower() for m in no_name_markers):
            return None, s
        return name or None, title or None
    if any(m in lowered for m in no_name_markers):
        return None, s
    return s or None, None


# ---- generic ingest ----

def ingest_pipeline_rows(db, client, rows, source, pmf_weight=0.8, rs_weight=0.2):
    """
    Load rows (list of dict) into the pipeline for a given client.
    Auto-detects columns. Idempotent. Returns a summary dict.
    """
    if not rows:
        return {"imported": 0, "updated": 0, "skipped": 0}

    cmap = _colmap(rows[0].keys())
    if not cmap["name"]:
        raise ValueError("No company/name column found in CSV.")

    imported = updated = 0
    tier_counts = {}

    for row in rows:
        name = (row.get(cmap["name"]) or "").strip()
        if not name:
            continue

        # fit -> pmf
        fit_raw = row.get(cmap["fit"]) if cmap["fit"] else None
        try:
            fit = int(float(fit_raw))
        except (TypeError, ValueError):
            fit = 0
        pmf = (max(0, min(fit, 5)) / 5.0) * 100.0 if fit else None

        # relationship strength: warm group ties get a lift
        accel = (row.get(cmap["accelerant"]) or "") if cmap["accelerant"] else ""
        rs = 3 if "WARM" in accel.upper() else 0

        signal = (row.get(cmap["signal"]) or "").strip() if cmap["signal"] else ""
        city, state = _parse_hq(row.get(cmap["hq"]) if cmap["hq"] else None)
        contact_name, contact_title = _parse_contact(
            row.get(cmap["contact"]) if cmap["contact"] else None
        )

        # --- prospect (find or create) ---
        prospect = db.query(Prospect).filter(Prospect.name.ilike(name)).first()
        is_new = prospect is None
        if is_new:
            prospect = Prospect(name=name)
            db.add(prospect)
        prospect.type = (row.get(cmap["type"]) or prospect.type) if cmap["type"] else prospect.type
        prospect.hq_city = city or prospect.hq_city
        prospect.hq_state = state or prospect.hq_state
        if cmap["desc"] and row.get(cmap["desc"]):
            prospect.description = row.get(cmap["desc"])
        if contact_name:
            prospect.decision_makers_json = json.dumps(
                [{"name": contact_name, "title": contact_title, "source": "web search"}]
            )
        prospect.enrichment_source = "web search"
        prospect.enrichment_date = datetime.utcnow()
        db.flush()

        # --- relationship (contact) ---
        if contact_name:
            rel = (
                db.query(Relationship)
                .filter(
                    Relationship.prospect_id == prospect.id,
                    Relationship.contact_name == contact_name,
                )
                .first()
            )
            if not rel:
                rel = Relationship(prospect_id=prospect.id, contact_name=contact_name)
                db.add(rel)
            rel.contact_title = contact_title
            rel.score = rs
            rel.context = signal or None
            rel.source = "web search"
            rel.warmest_path = "Warm group tie" if rs >= 3 else "Cold / direct"
            db.flush()

        # --- pipeline entry ---
        entry = (
            db.query(PipelineEntry)
            .filter(
                PipelineEntry.client_id == client.id,
                PipelineEntry.prospect_id == prospect.id,
            )
            .first()
        )
        entry_new = entry is None
        if entry_new:
            entry = PipelineEntry(client_id=client.id, prospect_id=prospect.id)
            db.add(entry)
        entry.source = source
        entry.notes = signal or entry.notes
        entry.pmf_weight = pmf_weight
        entry.rs_weight = rs_weight
        entry.relationship_score = rs

        if pmf is not None:
            matchmaker = calculate_matchmaker(pmf, rs, pmf_weight, rs_weight)
            entry.pmf_score = round(pmf, 1)
            entry.matchmaker_score = round(matchmaker, 1)
            entry.tier = assign_tier(matchmaker)
            entry.status = "scored"
        db.flush()

        tier_counts[entry.tier] = tier_counts.get(entry.tier, 0) + 1
        if entry_new:
            imported += 1
        else:
            updated += 1

    db.add(ActivityLog(
        action="pipeline_imported",
        new_value=f"Imported {imported} + updated {updated} accounts for {client.name}",
        notes=source,
    ))
    db.commit()
    return {"imported": imported, "updated": updated, "tiers": tier_counts}


# ---- Decerto-specific loader ----

DECERTO_CRITERIA = [
    ("Legacy core-system signal", "Aging COBOL/mainframe or risky bespoke rebuild = displacement window", "Decerto replaces legacy cores", 10, 1),
    ("GWP band fit", "Inside the $500M-$5B sweet spot", "Big enough to fund a replacement, too small to already have a modern PAS", 8, 2),
    ("Modernization trigger", "An active 'why now' (COBOL hiring, stalled rebuild, new D2C strain)", "Timing drives the deal", 8, 3),
    ("Segment fit", "Mid-Tier P&C > Specialty/MGA > Reinsurance > Tier-1 modular", "Where Decerto wins", 6, 4),
    ("Buying-committee access", "Identifiable, reachable CIO/CTO/Head of Digital", "A path in", 5, 5),
]


def import_decerto(db, csv_path=None):
    """Load the Decerto client, criteria, and scored prospect pipeline. Idempotent."""
    csv_path = csv_path or os.path.join(REPO_ROOT, "decerto_prospects.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Decerto CSV not found at {csv_path}")

    # client
    client = db.query(Client).filter(Client.name == "Decerto").first()
    if not client:
        client = Client(name="Decerto")
        db.add(client)
    client.website = "https://www.decerto.com/us"
    client.description = "Modular, API-first insurance core software (PAS + Higson rules engine) for P&C, Life, Health, Group. Replaces aging legacy cores at mid-tier carriers."
    client.primary_revenue_driver = "Core-platform / PAS modernization deals with carriers"
    client.target_buyer = "Mid-tier P&C carriers ($500M-$5B GWP) running aging legacy cores"
    client.profile_json = json.dumps({
        "hq": "Warsaw, Poland (US GTM)", "founded": 2006,
        "flagship": "Higson business-rules / rating engine",
        "notable_clients": ["Allianz", "Generali", "Talanx", "Warta", "Aviva", "Sompo"],
        "buying_committee": ["CIO / CTO / Head of IT", "Head of Distribution", "Head of Digital / COO"],
    })
    db.flush()

    # criteria (create once)
    existing = {c.name for c in db.query(ScoringCriterion).filter(ScoringCriterion.client_id == client.id)}
    for name, desc, why, weight, order in DECERTO_CRITERIA:
        if name not in existing:
            db.add(ScoringCriterion(
                client_id=client.id, name=name, description=desc,
                why_it_matters=why, weight=weight, sort_order=order,
            ))
    db.flush()

    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))

    return ingest_pipeline_rows(db, client, rows, source="Decerto US Prospect List")
