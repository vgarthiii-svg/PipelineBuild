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
    BehaviorProfile, IdentityFilter, CriteriaLibrary,
)
from app.scoring import calculate_pmf, calculate_matchmaker, assign_tier


def seed_database(db: Session):
    """Run full seed if database is empty."""
    if db.query(Client).count() > 0:
        return

    print("[SEED] Seeding database with initial data...")

    # ---- 0. Criteria Library (20 criteria in 4 groups) ----
    _seed_criteria_library(db)

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
    # Link Tivly's criteria to the library entries
    tivly_criteria_names = [
        "Distribution Alignment", "SMB Commercial Focus",
        "Digital CX / Acquisition", "Lead Gen Compatibility",
    ]
    criteria_objs = {}
    for cname in tivly_criteria_names:
        lib_entry = db.query(CriteriaLibrary).filter(CriteriaLibrary.name == cname).first()
        if lib_entry:
            c = ScoringCriterion(
                client_id=tivly.id,
                library_id=lib_entry.id,
                name=lib_entry.name,
                description=lib_entry.description,
                why_it_matters=lib_entry.why_it_matters,
                weight=lib_entry.default_weight,
                sort_order=lib_entry.sort_order,
                active=True,
                group_name=lib_entry.group_name,
            )
            db.add(c)
            db.flush()
            criteria_objs[cname] = c

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

    # ---- 7. v2: Tivly behavior profile ----
    # Create a prospect record for Tivly so it can have a behavior profile
    tivly_prospect = db.query(Prospect).filter(Prospect.name.ilike("Tivly")).first()
    if not tivly_prospect:
        tivly_prospect = Prospect(
            name="Tivly",
            type="Marketplace",
            industry_vertical="InsurTech",
            business_model="B2B",
            stage="growth",
        )
        db.add(tivly_prospect)
        db.flush()

    tivly_behavior = BehaviorProfile(
        prospect_id=tivly_prospect.id,
        sales_motion="consultative",
        partner_model="managed",
        decision_speed="moderate",
        culture="innovation-forward",
        customer_segment="SMB",
        partnership_history="Active reseller and referral partner model. Open to new distribution partnerships.",
        assessed_by="seed",
        assessed_at=datetime.utcnow(),
    )
    db.add(tivly_behavior)

    # ---- 8. v2: Tivly identity filter ----
    tivly_filter = IdentityFilter(
        client_id=tivly.id,
        allowed_business_models=json.dumps(["B2B", "SaaS", "hybrid"]),
        allowed_stages=json.dumps(["growth", "mature", "enterprise"]),
        min_employees=10,
        excluded_verticals=json.dumps(["Life Insurance", "Health Insurance"]),
        notes="Tivly targets commercial P&C carriers, MGAs, and insurtechs",
    )
    db.add(tivly_filter)

    # ---- 9. v2: Backfill prospect identity fields ----
    type_mapping = {
        "Regional Carrier": {"industry_vertical": "P&C Insurance", "business_model": "B2B", "stage": "mature"},
        "National Carrier": {"industry_vertical": "P&C Insurance", "business_model": "B2B", "stage": "enterprise"},
        "Specialty Carrier": {"industry_vertical": "P&C Insurance", "business_model": "B2B", "stage": "mature"},
        "National Brokerage": {"industry_vertical": "P&C Insurance", "business_model": "B2B", "stage": "enterprise"},
        "National Agency": {"industry_vertical": "P&C Insurance", "business_model": "B2B", "stage": "growth"},
        "Wholesale Broker": {"industry_vertical": "P&C Insurance", "business_model": "B2B", "stage": "mature"},
        "Technology": {"industry_vertical": "InsurTech", "business_model": "SaaS", "stage": "growth"},
        "Marketplace": {"industry_vertical": "InsurTech", "business_model": "B2B", "stage": "growth"},
    }
    all_prospects = db.query(Prospect).all()
    for p in all_prospects:
        if p.type and not p.industry_vertical:
            mapping = type_mapping.get(p.type, {})
            for key, val in mapping.items():
                setattr(p, key, val)

    # ---- 10. Initial activity log ----
    log = ActivityLog(
        action="system",
        new_value="Database seeded with Tivly client, 16 Scott Montgomery companies, 30 Guidewire partners, known relationships, behavior profiles, and identity filters (v2)",
    )
    db.add(log)

    db.commit()
    print(f"[SEED] Done. Clients: {db.query(Client).count()}, "
          f"Prospects: {db.query(Prospect).count()}, "
          f"Pipeline: {db.query(PipelineEntry).count()}, "
          f"Relationships: {db.query(Relationship).count()}, "
          f"Library criteria: {db.query(CriteriaLibrary).count()}")


def _seed_criteria_library(db: Session):
    """Seed the master criteria library with 20 criteria in 4 groups."""
    if db.query(CriteriaLibrary).count() > 0:
        return

    library = [
        # Group 1: Market Fit
        ("Market Fit", 1, "Operates in the same states as you", "They cover the same geographic footprint.", "Partners in the same geography can co-sell and share distribution", 4, 1, '["geographic", "region", "state", "territory", "footprint", "local"]'),
        ("Market Fit", 1, "Sells to the same customer type", "Same decision-maker title and same company profile.", "Shared buyer type means warm introductions carry more weight", 5, 2, '["buyer", "persona", "decision", "icp", "target", "sells to"]'),
        ("Market Fit", 1, "Targets the same segment size", "SMB, mid-market, or enterprise alignment.", "Segment alignment drives conversion on introductions", 4, 3, '["smb", "mid-market", "enterprise", "segment", "size", "small business"]'),
        ("Market Fit", 1, "Focused on the same insurance lines", "Commercial, personal, or specialty line alignment.", "Vertical match means the prospect already understands the client's world", 4, 4, '["vertical", "commercial", "personal", "specialty", "lines", "workers comp", "auto"]'),
        ("Market Fit", 1, "Specializes in small commercial", "Small commercial is a distinct market with its own distribution needs.", "SMB commercial is a distinct market with unique distribution needs", 5, 5, '["smb", "small commercial", "small business", "commercial lines"]'),

        # Group 2: Product & Technology
        ("Product & Technology", 2, "Product pairs with yours", "Their offering naturally complements what you sell.", "Partners whose products pair with the client create stronger value propositions", 5, 1, '["product", "complement", "pair", "adjacent", "value chain"]'),
        ("Product & Technology", 2, "Has APIs you could integrate with", "Open APIs, integration partnerships, or platform connectivity.", "API-ready companies integrate faster, reducing time-to-value", 4, 2, '["api", "integration", "connect", "platform", "plug", "webhook", "rest"]'),
        ("Product & Technology", 2, "Runs on a compatible core system", "Guidewire, Duck Creek, Majesco, or similar stack alignment.", "Stack compatibility reduces friction in joint implementations", 3, 3, '["guidewire", "duck creek", "majesco", "stack", "platform", "core system"]'),
        ("Product & Technology", 2, "Brings data or analytics", "Data, AI, or analytics that strengthen your value chain.", "Data partnerships compound over time and create switching costs", 4, 4, '["data", "analytics", "ai", "machine learning", "intelligence", "predictive"]'),
        ("Product & Technology", 2, "Strengthens digital customer experience", "Improves the online buying journey for end customers.", "Digital experience drives conversion and retention in modern distribution", 4, 5, '["digital", "cx", "customer experience", "online", "self-service", "portal", "ux"]'),
        ("Product & Technology", 2, "Can generate or share leads", "Lead-gen capabilities that fit your distribution model.", "Direct product-market fit signal for distribution partnerships", 5, 6, '["lead", "demand", "referral", "marketing", "acquisition", "traffic"]'),

        # Group 3: Business Dynamics
        ("Business Dynamics", 3, "Focuses on distribution, not claims", "Growth-side of the business, not just loss adjustment.", "Distribution-focused partners are stronger fits for growth partnerships", 5, 1, '["distribution", "channel", "underwriting", "policy", "new business"]'),
        ("Business Dynamics", 3, "Revenue model fits yours", "SaaS, transactional, or per-policy economics align.", "Mismatched revenue models create friction in deal structure", 3, 2, '["revenue", "saas", "transactional", "per-policy", "subscription", "pricing"]'),
        ("Business Dynamics", 3, "Has partnered successfully before", "Track record with similar companies. They know how to partner.", "Companies with partner DNA close deals faster", 4, 3, '["partnership", "partner", "alliance", "joint", "co-sell", "reseller"]'),
        ("Business Dynamics", 3, "Market position supports the deal", "Leader, challenger, or niche. Affects deal leverage and priority.", "Position affects deal leverage and partnership priority", 3, 4, '["leader", "challenger", "niche", "market share", "competitive", "dominant"]'),
        ("Business Dynamics", 3, "Licensed where you need them", "Regulatory coverage in the states that matter for this deal.", "Regulatory gaps can block distribution deals entirely", 3, 5, '["regulatory", "compliance", "licensed", "filing", "admitted", "surplus"]'),

        # Group 4: Relationship & Timing
        ("Relationship & Timing", 4, "You can reach the right person", "The decision maker is accessible through your network.", "Accessible decision makers shorten deal cycles dramatically", 5, 1, '["decision maker", "accessible", "contact", "reach", "intro", "connection"]'),
        ("Relationship & Timing", 4, "Sales cycle matches yours", "Buying and selling speed don't create friction.", "Mismatched cycles create frustration and stalled deals", 3, 2, '["sales cycle", "speed", "fast", "slow", "bureaucratic", "agile"]'),
        ("Relationship & Timing", 4, "Partnerships are a current priority", "They're actively looking to partner right now.", "Partners who are actively seeking align faster", 4, 3, '["strategic", "priority", "initiative", "focus", "roadmap", "expansion"]'),
        ("Relationship & Timing", 4, "You'll see them at upcoming events", "In-person meetings at conferences accelerate the relationship.", "In-person meetings at events dramatically accelerate relationship building", 3, 4, '["conference", "event", "air", "itc", "meeting", "attend"]'),
    ]

    for group, gorder, name, desc, why, weight, sorder, keywords in library:
        entry = CriteriaLibrary(
            group_name=group,
            group_order=gorder,
            name=name,
            description=desc,
            why_it_matters=why,
            default_weight=weight,
            sort_order=sorder,
            heuristic_keywords=keywords,
        )
        db.add(entry)

    db.flush()
    print(f"[SEED] Criteria library: {db.query(CriteriaLibrary).count()} criteria in 4 groups")
