from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, Date, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    website = Column(String)
    description = Column(Text)
    primary_revenue_driver = Column(Text)
    target_buyer = Column(Text)
    profile_json = Column(Text)
    active = Column(Boolean, default=False)  # True = actively representing, False = scored only
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    criteria = relationship("ScoringCriterion", back_populates="client", cascade="all, delete-orphan")
    pipeline_entries = relationship("PipelineEntry", back_populates="client")
    identity_filter = relationship("IdentityFilter", uselist=False, back_populates="client", cascade="all, delete-orphan")


class CriteriaLibrary(Base):
    """Master library of 20 pre-built scoring criteria organized in 4 groups."""
    __tablename__ = "criteria_library"

    id = Column(Integer, primary_key=True, index=True)
    group_name = Column(String, nullable=False)     # "Market Fit", "Product & Technology", etc.
    group_order = Column(Integer, default=1)         # 1-4
    name = Column(String, nullable=False)            # "Geographic Overlap"
    description = Column(Text)                       # What it measures
    why_it_matters = Column(Text)                    # Why it matters for scoring
    default_weight = Column(Integer, default=5)      # Suggested weight 1-10
    sort_order = Column(Integer)                     # Order within group
    heuristic_keywords = Column(Text)                # JSON array of keywords for heuristic matching


class ScoringCriterion(Base):
    __tablename__ = "scoring_criteria"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    library_id = Column(Integer, ForeignKey("criteria_library.id"), nullable=True)  # Link to library
    name = Column(String, nullable=False)
    description = Column(Text)
    why_it_matters = Column(Text)
    weight = Column(Integer, default=5)
    sort_order = Column(Integer)
    active = Column(Boolean, default=True)           # Toggle on/off
    group_name = Column(String)                      # Inherited from library
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="criteria")
    criterion_scores = relationship("CriterionScore", back_populates="criterion")


class Prospect(Base):
    __tablename__ = "prospects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String)
    website = Column(String)
    domain = Column(String)
    alternate_domains = Column(Text)
    hq_city = Column(String)
    hq_state = Column(String)
    employees = Column(Integer)
    revenue = Column(String)
    description = Column(Text)
    decision_makers_json = Column(Text)
    enrichment_source = Column(String)
    enrichment_date = Column(DateTime)
    # v2: Identity layer fields
    industry_vertical = Column(String)
    sub_vertical = Column(String)
    business_model = Column(String)
    stage = Column(String)
    capability_provides = Column(Text)  # JSON array
    capability_needs = Column(Text)     # JSON array
    channels = Column(Text)            # JSON array
    tech_stack = Column(Text)          # JSON array
    regulatory_footprint = Column(Text) # JSON array
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pipeline_entries = relationship("PipelineEntry", back_populates="prospect")
    relationships = relationship("Relationship", back_populates="prospect")
    scans = relationship("RelationshipScan", back_populates="prospect")
    behavior_profile = relationship("BehaviorProfile", uselist=False, back_populates="prospect", cascade="all, delete-orphan")
    intent_signals = relationship("IntentSignal", back_populates="prospect", cascade="all, delete-orphan")
    business_profile = relationship("BusinessProfile", uselist=False, backref="prospect", cascade="all, delete-orphan")


class PipelineEntry(Base):
    __tablename__ = "pipeline_entries"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    prospect_id = Column(Integer, ForeignKey("prospects.id"), nullable=False)
    source = Column(String)
    source_date = Column(Date)
    source_priority = Column(String)
    tier = Column(String, default="unscored")
    pmf_score = Column(Float)
    relationship_score = Column(Integer, default=0)
    matchmaker_score = Column(Float)
    pmf_weight = Column(Float, default=0.6)
    rs_weight = Column(Float, default=0.4)
    status = Column(String, default="new")
    next_action = Column(Text)
    notes = Column(Text)
    # v2: 4-layer scoring fields
    filtered = Column(Boolean, default=False)
    filter_reason = Column(Text)
    friction_coefficient = Column(Float, default=1.0)
    intent_multiplier = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("client_id", "prospect_id", name="uq_client_prospect"),
    )

    client = relationship("Client", back_populates="pipeline_entries")
    prospect = relationship("Prospect", back_populates="pipeline_entries")
    criterion_scores = relationship("CriterionScore", back_populates="pipeline_entry", cascade="all, delete-orphan")
    intro_packages = relationship("IntroPackage", back_populates="pipeline_entry")
    activities = relationship("ActivityLog", back_populates="pipeline_entry")


class CriterionScore(Base):
    __tablename__ = "criterion_scores"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_entry_id = Column(Integer, ForeignKey("pipeline_entries.id"), nullable=False)
    criterion_id = Column(Integer, ForeignKey("scoring_criteria.id"), nullable=False)
    score = Column(Integer, default=0)
    reasoning = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    pipeline_entry = relationship("PipelineEntry", back_populates="criterion_scores")
    criterion = relationship("ScoringCriterion", back_populates="criterion_scores")


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id"), nullable=False)
    contact_name = Column(String)
    contact_title = Column(String)
    contact_email = Column(String)
    contact_linkedin = Column(String)
    score = Column(Integer, default=0)
    context = Column(Text)
    source = Column(String)
    last_touch = Column(Date)
    warmest_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    prospect = relationship("Prospect", back_populates="relationships")


class RelationshipScan(Base):
    __tablename__ = "relationship_scans"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id"), nullable=False)
    scan_date = Column(DateTime, default=datetime.utcnow)
    gmail_hits = Column(Integer, default=0)
    gmail_details = Column(Text)
    hubspot_hits = Column(Integer, default=0)
    hubspot_details = Column(Text)
    calendar_hits = Column(Integer, default=0)
    calendar_details = Column(Text)
    conference_hits = Column(Integer, default=0)
    conference_details = Column(Text)
    relationship_map_hits = Column(Integer, default=0)
    relationship_map_details = Column(Text)
    final_rs = Column(Integer)
    evidence_summary = Column(Text)

    prospect = relationship("Prospect", back_populates="scans")


class IntroPackage(Base):
    __tablename__ = "intro_packages"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_entry_id = Column(Integer, ForeignKey("pipeline_entries.id"), nullable=False)
    target_contact = Column(String)
    target_title = Column(String)
    email_subject = Column(String)
    email_body = Column(Text)
    talking_points = Column(Text)
    value_prop_prospect = Column(Text)
    value_prop_client = Column(Text)
    mutual_connections = Column(Text)
    objections_json = Column(Text)
    status = Column(String, default="draft")
    sent_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    pipeline_entry = relationship("PipelineEntry", back_populates="intro_packages")


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_entry_id = Column(Integer, ForeignKey("pipeline_entries.id"))
    action = Column(String)
    old_value = Column(Text)
    new_value = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    pipeline_entry = relationship("PipelineEntry", back_populates="activities")


class ConferenceAttendee(Base):
    __tablename__ = "conference_attendees"

    id = Column(Integer, primary_key=True, index=True)
    conference_name = Column(String)
    conference_date = Column(String)
    attendee_name = Column(String)
    title = Column(String)
    company = Column(String)
    city = Column(String)
    state = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============ v2: NOTIFICATIONS + AGENT ============


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False)       # "tier_change", "new_companies", "rescore_complete", "api_cost_pending"
    title = Column(String, nullable=False)
    detail = Column(Text)
    read = Column(Boolean, default=False)
    action_url = Column(String)                 # Optional link to relevant dashboard section
    created_at = Column(DateTime, default=datetime.utcnow)


class PendingApiAction(Base):
    """Queued API actions that require user approval before executing."""
    __tablename__ = "pending_api_actions"

    id = Column(Integer, primary_key=True, index=True)
    action_type = Column(String, nullable=False)    # "generate_intro", "research_intent", "profile_client"
    description = Column(Text, nullable=False)       # Human-readable description of what will happen
    params_json = Column(Text, nullable=False)       # JSON blob of parameters needed to execute
    status = Column(String, default="pending")       # "pending", "approved", "rejected", "executed"
    estimated_cost = Column(String)                  # "$0.01-0.03" etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)


# ============ v2: NEW TABLES ============


class BehaviorProfile(Base):
    __tablename__ = "behavior_profiles"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id"), unique=True, nullable=False)
    sales_motion = Column(String)       # "transactional", "consultative", "enterprise"
    partner_model = Column(String)      # "self-serve", "managed", "co-sell", "unknown"
    decision_speed = Column(String)     # "fast", "moderate", "bureaucratic"
    culture = Column(String)            # "innovation-forward", "balanced", "legacy"
    customer_segment = Column(String)   # "SMB", "mid-market", "enterprise", "mixed"
    partnership_history = Column(Text)
    notes = Column(Text)
    assessed_by = Column(String, default="manual")  # "claude", "manual", "seed"
    assessed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    prospect = relationship("Prospect", back_populates="behavior_profile")


class IntentSignal(Base):
    __tablename__ = "intent_signals"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id"), nullable=False)
    signal_type = Column(String, nullable=False)   # "hiring", "expansion", "funding", etc.
    signal_detail = Column(Text, nullable=False)
    signal_date = Column(Date)
    urgency = Column(String, default="moderate")    # "high", "moderate", "low"
    relevance_note = Column(Text)
    source_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    prospect = relationship("Prospect", back_populates="intent_signals")


class BusinessProfile(Base):
    """One business profile per prospect. Supports tiered generation."""
    __tablename__ = "business_profiles"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id"), unique=True, nullable=False)

    # Overview
    one_liner = Column(Text)
    long_description = Column(Text)
    founded_year = Column(Integer)
    headquarters = Column(String)

    # Products & Services
    primary_products = Column(Text)       # JSON array
    secondary_products = Column(Text)     # JSON array
    flagship_product = Column(String)

    # Market
    target_customer_types = Column(Text)  # JSON array
    target_segments = Column(Text)        # JSON array
    target_verticals = Column(Text)       # JSON array
    geographic_markets = Column(Text)     # JSON array

    # Go-to-Market
    sales_channels = Column(Text)         # JSON array
    pricing_model = Column(String)
    typical_deal_size = Column(String)

    # Value Chain
    value_chain_upstream = Column(Text)   # JSON array
    value_chain_downstream = Column(Text) # JSON array
    key_integrations = Column(Text)       # JSON array

    # Competitive Landscape
    main_competitors = Column(Text)       # JSON array of {name, differentiator}
    key_differentiators = Column(Text)
    market_position = Column(String)      # "leader", "challenger", "niche"

    # Signals
    recent_developments = Column(Text)    # JSON array
    growth_indicators = Column(Text)

    # Metadata
    generated_by = Column(String, default="heuristic")  # "heuristic", "enrichment", "claude", "manual"
    generation_depth = Column(String, default="basic")  # "basic", "enriched", "deep", "full"
    confidence_score = Column(Integer, default=20)      # 0-100
    last_refreshed = Column(DateTime, default=datetime.utcnow)
    refresh_due = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IdentityFilter(Base):
    __tablename__ = "identity_filters"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), unique=True, nullable=False)
    allowed_business_models = Column(Text)   # JSON array
    allowed_stages = Column(Text)            # JSON array
    min_employees = Column(Integer)
    max_employees = Column(Integer)
    required_verticals = Column(Text)        # JSON array
    excluded_verticals = Column(Text)        # JSON array
    required_states = Column(Text)           # JSON array
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", back_populates="identity_filter")


class ScheduledJob(Base):
    """
    Registry of background jobs the agent layer runs on a schedule.
    Each job is keyed by `job_key` (matches a function in scheduler.py).
    """
    __tablename__ = "scheduled_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_key = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    schedule = Column(String, nullable=False)  # "daily@03:00", "weekly@mon@04:00", "hourly"
    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime)
    last_status = Column(String)   # "ok" | "error" | "running"
    last_output = Column(Text)
    next_run = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============ Fantasy Football: PPR Draft Rankings ============


class PlayerRanking(Base):
    """
    A fantasy-football player row imported from a rankings CSV. Powers the
    PPR Draft Board: filterable by position/tier and click-through to a
    full player profile. `source` lets multiple ranking sets coexist.
    """
    __tablename__ = "player_rankings"
    __table_args__ = (UniqueConstraint("source", "player_id", name="uq_source_player"),)

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, default="REDRAFT PPR", index=True)
    player_id = Column(Integer, index=True)      # external id from the source file
    rank = Column(Integer, index=True)           # overall rank in this source
    name = Column(String, nullable=False, index=True)
    team = Column(String)                        # may be blank (free agent)
    position = Column(String, index=True)        # QB/RB/WR/TE
    tier = Column(String, index=True)            # S/A/B/... letter tier
    mason_dodd_rank = Column(Integer)            # nullable ('-' in source)
    expert_rank = Column(Float)                  # consensus/expert rank, nullable
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============ Fantasy Football: Live Draft Tracker ============


class DraftSession(Base):
    """
    One live draft. Tracks the ranking source it drafts against, the league
    shape (teams, rounds, snake), the on-the-clock position, and the teams
    (as JSON: [{slot, name, owner_tag}], owner_tag in {"me","jake",null}).
    """
    __tablename__ = "draft_sessions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="Live Draft")
    source = Column(String, nullable=False)          # ranking source to draft against
    num_teams = Column(Integer, default=12)
    rounds = Column(Integer, default=16)
    snake = Column(Boolean, default=True)
    current_pick = Column(Integer, default=1)        # 1-based overall pick on the clock
    teams_json = Column(Text)                         # JSON list of team slots
    espn_league_id = Column(String)                  # optional, for ESPN sync
    espn_season = Column(Integer)                     # optional season year
    status = Column(String, default="active")        # "active" | "complete"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    picks = relationship("DraftPick", back_populates="session", cascade="all, delete-orphan")


class DraftPick(Base):
    """A single selection in a draft session."""
    __tablename__ = "draft_picks"
    __table_args__ = (UniqueConstraint("session_id", "overall_pick", name="uq_session_pick"),)

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("draft_sessions.id"), nullable=False, index=True)
    overall_pick = Column(Integer, nullable=False)   # 1-based
    round = Column(Integer)
    pick_in_round = Column(Integer)
    team_slot = Column(Integer)                       # which team made the pick
    player_id = Column(Integer)                       # from player_rankings, nullable for manual
    player_name = Column(String, nullable=False)
    position = Column(String)
    nfl_team = Column(String)
    source_rank = Column(Integer)                     # player's rank in the draft source when taken
    via = Column(String, default="manual")            # "manual" | "espn"
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("DraftSession", back_populates="picks")
