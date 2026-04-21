"""
Seed data for the BD Pipeline Agent.

Imports on first run:
- Tivly client profile + 4 scoring criteria
- 16 Scott Montgomery prospect companies + pipeline entries
- Known relationships (Sentry RS:5, Erie RS:2, etc.)
- Guidewire ecosystem (30 partners) with pre-scored pipeline entries
- Known AIR 2025 conference attendees
"""

import csv
import json
import os
from datetime import date, datetime
from sqlalchemy.orm import Session

from app.models import (
    Client, ScoringCriterion, Prospect, PipelineEntry,
    CriterionScore, Relationship, ConferenceAttendee, ActivityLog,
)
from app.scoring import calculate_pmf, calculate_matchmaker, assign_tier


def seed_database(db: Session):
    """Run full seed if database is empty."""
    if db.query(Client).count() > 0:
        return

    print("[SEED] Seeding database with initial data...")

    # ---- 1. Tivly Client ----
    tivly = Client(
        name="Tivly",
        website="https://tivly.com",
        description="Digital commercial insurance marketplace connecting SMBs to 350+ insurance providers. 70K+ connections/month, 1.4M businesses annually.",
        primary_revenue_driver="Commercial insurance lead generation and smart matching technology",
        target_buyer="Insurance carriers and agencies needing SMB commercial distribution",
        profile_json=json.dumps({
            "hq": "St. Petersburg, FL",
            "founded": 2009,
            "employees": "200+",
            "revenue": "$250-500M",
            "funding": "$26M",
            "ownership": "Subsidiary of INSURICA",
            "products": [
                "Commercial insurance lead generation (70K+ connections/month)",
                "Smart matching technology (350+ insurance providers)",
                "Digital optimization and call center services",
            ],
            "go_to_market": "Digital marketplace + call center. Channel partnerships with carriers, agencies, MGAs.",
            "problems_solved": [
                "SMBs can't find the right commercial coverage quickly",
                "Carriers struggle to reach small commercial customers efficiently",
                "Agents need lead flow without building their own acquisition engine",
            ],
        }),
    )
    db.add(tivly)
    db.flush()

    # ---- 2. Tivly Scoring Criteria ----
    criteria_data = [
        ("Distribution Alignment", "Works in policy/underwriting/digital distribution vs claims-only", "Tivly generates leads for new business, not claims", 5, 1),
        ("SMB Commercial Focus", "Focused on small commercial lines", "Tivly's marketplace is SMB-focused", 5, 2),
        ("Digital CX / Acquisition", "Improves digital customer journey", "Tivly's value prop is simplifying the buying journey", 4, 3),
        ("Lead Gen Compatibility", "Could benefit from or complement Tivly's lead generation", "Direct product-market fit signal", 5, 4),
    ]
    criteria_objs = {}
    for name, desc, why, weight, order in criteria_data:
        c = ScoringCriterion(
            client_id=tivly.id, name=name, description=desc,
            why_it_matters=why, weight=weight, sort_order=order,
        )
        db.add(c)
        db.flush()
        criteria_objs[name] = c

    # ---- 3. Scott Montgomery's 16 Companies ----
    scott_companies = [
        ("Grange", "Regional Carrier"),
        ("Sentry", "Regional Carrier"),
        ("Amtrust", "Specialty Carrier"),
        ("State Farm", "National Carrier"),
        ("Shelter", "Regional Carrier"),
        ("Assured Partners", "National Brokerage"),
        ("Goosehead", "National Agency"),
        ("Selective", "Regional Carrier"),
        ("NatGen", "Specialty Carrier"),
        ("Country Financial", "Regional Carrier"),
        ("Westfield", "Regional Carrier"),
        ("Erie", "Regional Carrier"),
        ("Cincinnati", "Regional Carrier"),
        ("Guard", "Specialty Carrier"),
        ("CRC", "Wholesale Broker"),
        ("McGriff", "National Brokerage"),
    ]

    scott_prospects = {}
    for name, ptype in scott_companies:
        p = Prospect(name=name, type=ptype)
        db.add(p)
        db.flush()
        scott_prospects[name] = p

        # Create pipeline entry
        source_priority = "first-mentioned" if name in ("Erie", "Cincinnati") else "standard"
        source_date_val = date(2026, 3, 6) if name in ("Erie", "Cincinnati") else date(2026, 3, 27)

        entry = PipelineEntry(
            client_id=tivly.id,
            prospect_id=p.id,
            source="Scott Montgomery email",
            source_date=source_date_val,
            source_priority=source_priority,
        )
        db.add(entry)
        db.flush()

    # ---- 4. Known Relationships ----
    relationships_data = [
        ("Sentry", "Richard Learey", "BD, Dairyland", None, 5,
         "Former employer ~20 years. Active email relationship. Made introductions on Vinnie's behalf.",
         "gmail", "Direct"),
        ("Erie", "Cody Cook", "EVP Claims", None, 2,
         "CRM contact. No direct email threads.",
         "hubspot", "Via HubSpot CRM"),
        ("Erie", "Danielle Hermann", "Dir Agent Marketing", None, 2,
         "AIR 2025 conference attendee.",
         "conference", "AIR 2025 co-attendee"),
        ("State Farm", "Brian Tira", "Dir Financial Ops", None, 1,
         "Same industry dinner invite 2021, AIR 2025 attendee. Peripheral.",
         "conference", "AIR 2025 co-attendee"),
        ("Cincinnati", "Scott Kelly", "AVP Product Mgmt", None, 1,
         "Conference attendee only.",
         "conference", "AIR 2025 co-attendee"),
        ("Country Financial", "Andrew Walter", "Mgr PL Data/Analytics", None, 1,
         "Conference attendee only. PL/data title, not commercial distribution.",
         "conference", "AIR 2025 co-attendee"),
    ]

    for company, contact, title, email, score, context, source, path in relationships_data:
        prospect = scott_prospects.get(company)
        if prospect:
            rel = Relationship(
                prospect_id=prospect.id,
                contact_name=contact,
                contact_title=title,
                contact_email=email,
                score=score,
                context=context,
                source=source,
                warmest_path=path,
                last_touch=date(2026, 4, 1),
            )
            db.add(rel)

            # Update pipeline entry RS
            entry = (
                db.query(PipelineEntry)
                .filter(PipelineEntry.prospect_id == prospect.id, PipelineEntry.client_id == tivly.id)
                .first()
            )
            if entry and score > entry.relationship_score:
                entry.relationship_score = score

    db.flush()

    # ---- 5. Guidewire Ecosystem ----
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "guidewire_ecosystem.csv")
    if os.path.exists(csv_path):
        print("[SEED] Importing Guidewire ecosystem...")
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Partner Name", "").strip()
                if not name:
                    continue

                # Check if already exists (from Scott's list)
                existing = db.query(Prospect).filter(Prospect.name.ilike(name)).first()
                if not existing:
                    p = Prospect(
                        name=name,
                        type=row.get("Partner Type", "Technology"),
                    )
                    db.add(p)
                    db.flush()
                else:
                    p = existing

                # Create pipeline entry if not exists
                existing_entry = (
                    db.query(PipelineEntry)
                    .filter(PipelineEntry.client_id == tivly.id, PipelineEntry.prospect_id == p.id)
                    .first()
                )
                if not existing_entry:
                    entry = PipelineEntry(
                        client_id=tivly.id,
                        prospect_id=p.id,
                        source="Guidewire Marketplace",
                    )
                    db.add(entry)
                    db.flush()

                    # Pre-score from CSV data
                    score_map = {
                        "Tivly Dist Align": "Distribution Alignment",
                        "Tivly SMB Focus": "SMB Commercial Focus",
                        "Tivly Digital CX": "Digital CX / Acquisition",
                        "Tivly Lead Gen Fit": "Lead Gen Compatibility",
                    }
                    scores_and_weights = []
                    for csv_col, criterion_name in score_map.items():
                        raw = row.get(csv_col, "0")
                        try:
                            score_val = int(raw)
                        except (ValueError, TypeError):
                            score_val = 0

                        criterion = criteria_objs.get(criterion_name)
                        if criterion:
                            cs = CriterionScore(
                                pipeline_entry_id=entry.id,
                                criterion_id=criterion.id,
                                score=score_val,
                                reasoning="Pre-scored from Guidewire ecosystem analysis",
                            )
                            db.add(cs)
                            scores_and_weights.append((score_val, criterion.weight))

                    # Calculate scores
                    if scores_and_weights:
                        pmf = calculate_pmf(scores_and_weights)
                        matchmaker = calculate_matchmaker(pmf, entry.relationship_score)
                        entry.pmf_score = round(pmf, 1)
                        entry.matchmaker_score = round(matchmaker, 1)
                        entry.tier = assign_tier(matchmaker)
                        entry.status = "scored"
    else:
        print(f"[SEED] Guidewire CSV not found at {csv_path}, skipping.")

    # ---- 6. Conference Attendees (known from relationship data) ----
    attendees_data = [
        ("AIR 2025", "Danielle Hermann", "Dir Agent Marketing", "Erie", None, None),
        ("AIR 2025", "Brian Tira", "Dir Financial Ops", "State Farm", None, None),
        ("AIR 2025", "Scott Kelly", "AVP Product Mgmt", "Cincinnati", None, None),
        ("AIR 2025", "Andrew Walter", "Mgr PL Data/Analytics", "Country Financial", None, None),
        ("AIR 2025", "Cody Cook", "EVP Claims", "Erie", None, None),
    ]
    for conf, name, title, company, city, state in attendees_data:
        att = ConferenceAttendee(
            conference_name=conf,
            attendee_name=name,
            title=title,
            company=company,
            city=city,
            state=state,
        )
        db.add(att)

    # ---- 7. Initial activity log ----
    log = ActivityLog(
        action="system",
        new_value="Database seeded with Tivly client, 16 Scott Montgomery companies, 30 Guidewire partners, and known relationships",
    )
    db.add(log)

    db.commit()
    print(f"[SEED] Done. Clients: {db.query(Client).count()}, "
          f"Prospects: {db.query(Prospect).count()}, "
          f"Pipeline: {db.query(PipelineEntry).count()}, "
          f"Relationships: {db.query(Relationship).count()}")
