from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date


# ---- Clients ----

class ClientCreate(BaseModel):
    name: str
    website: Optional[str] = None
    description: Optional[str] = None
    primary_revenue_driver: Optional[str] = None
    target_buyer: Optional[str] = None
    profile_json: Optional[str] = None


class ClientOut(BaseModel):
    id: int
    name: str
    website: Optional[str]
    description: Optional[str]
    primary_revenue_driver: Optional[str]
    target_buyer: Optional[str]
    active: bool = False
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class CriterionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    why_it_matters: Optional[str] = None
    weight: int = 5
    sort_order: Optional[int] = None


class CriterionOut(BaseModel):
    id: int
    client_id: int
    name: str
    description: Optional[str]
    why_it_matters: Optional[str]
    weight: int
    sort_order: Optional[int]

    class Config:
        from_attributes = True


# ---- Prospects ----

class ProspectCreate(BaseModel):
    name: str
    type: Optional[str] = None
    website: Optional[str] = None
    domain: Optional[str] = None
    alternate_domains: Optional[str] = None
    hq_city: Optional[str] = None
    hq_state: Optional[str] = None
    employees: Optional[int] = None
    revenue: Optional[str] = None
    description: Optional[str] = None


class ProspectOut(BaseModel):
    id: int
    name: str
    type: Optional[str]
    website: Optional[str]
    domain: Optional[str]
    hq_city: Optional[str]
    hq_state: Optional[str]
    employees: Optional[int]
    revenue: Optional[str]
    description: Optional[str]
    enrichment_source: Optional[str]
    industry_vertical: Optional[str] = None
    sub_vertical: Optional[str] = None
    business_model: Optional[str] = None
    stage: Optional[str] = None
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class BulkProspectCreate(BaseModel):
    names: List[str]


# ---- Pipeline ----

class PipelineEntryCreate(BaseModel):
    client_id: int
    prospect_id: int
    source: Optional[str] = None
    source_date: Optional[date] = None
    source_priority: Optional[str] = "standard"


class PipelineEntryOut(BaseModel):
    id: int
    client_id: int
    prospect_id: int
    source: Optional[str]
    tier: str
    pmf_score: Optional[float]
    relationship_score: int
    matchmaker_score: Optional[float]
    pmf_weight: float
    rs_weight: float
    status: str
    next_action: Optional[str]
    notes: Optional[str]
    prospect_name: Optional[str] = None
    prospect_type: Optional[str] = None
    best_contact: Optional[str] = None
    warmest_path: Optional[str] = None
    filtered: bool = False
    filter_reason: Optional[str] = None
    friction_coefficient: float = 1.0
    intent_multiplier: float = 1.0
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class PipelineWeightUpdate(BaseModel):
    pmf_weight: float = 0.6
    rs_weight: float = 0.4


class PipelineBulkCreate(BaseModel):
    client_id: int
    prospect_ids: List[int]
    source: Optional[str] = None
    source_date: Optional[date] = None


class CriterionScoreCreate(BaseModel):
    criterion_id: int
    score: int  # 0-5
    reasoning: Optional[str] = None


class CriterionScoreOut(BaseModel):
    id: int
    criterion_id: int
    score: int
    reasoning: Optional[str]
    criterion_name: Optional[str] = None
    criterion_weight: Optional[int] = None

    class Config:
        from_attributes = True


# ---- Relationships ----

class RelationshipCreate(BaseModel):
    prospect_id: int
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    contact_linkedin: Optional[str] = None
    score: int = 0
    context: Optional[str] = None
    source: Optional[str] = "manual"
    last_touch: Optional[date] = None
    warmest_path: Optional[str] = None


class RelationshipOut(BaseModel):
    id: int
    prospect_id: int
    contact_name: Optional[str]
    contact_title: Optional[str]
    contact_email: Optional[str]
    score: int
    context: Optional[str]
    source: Optional[str]
    last_touch: Optional[date]
    warmest_path: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# ---- Intro Packages ----

class IntroPackageOut(BaseModel):
    id: int
    pipeline_entry_id: int
    target_contact: Optional[str]
    target_title: Optional[str]
    email_subject: Optional[str]
    email_body: Optional[str]
    talking_points: Optional[str]
    value_prop_prospect: Optional[str]
    value_prop_client: Optional[str]
    mutual_connections: Optional[str]
    objections_json: Optional[str]
    status: str
    sent_date: Optional[datetime]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class IntroPackageUpdate(BaseModel):
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    talking_points: Optional[str] = None
    status: Optional[str] = None


class DraftTrackerItem(BaseModel):
    """A single row in the Draft Tracker: one intro package with pipeline context."""
    id: int
    pipeline_entry_id: int
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    prospect_id: Optional[int] = None
    prospect_name: Optional[str] = None
    target_contact: Optional[str] = None
    target_title: Optional[str] = None
    email_subject: Optional[str] = None
    status: str
    tier: Optional[str] = None
    matchmaker_score: Optional[float] = None
    sent_date: Optional[datetime] = None
    created_at: Optional[datetime] = None


class DraftTrackerSummary(BaseModel):
    total: int
    draft: int
    approved: int
    sent: int


class DraftTrackerOut(BaseModel):
    summary: DraftTrackerSummary
    items: List[DraftTrackerItem]


# ---- PPR Draft Rankings (fantasy football) ----

class PlayerRankingOut(BaseModel):
    id: int
    source: str
    player_id: Optional[int] = None
    rank: Optional[int] = None
    name: str
    team: Optional[str] = None
    position: Optional[str] = None
    position_rank: Optional[int] = None      # rank within position (e.g. RB4), computed
    tier: Optional[str] = None
    mason_dodd_rank: Optional[int] = None
    expert_rank: Optional[float] = None
    value_delta: Optional[float] = None       # expert_rank - rank (positive = value pick)

    class Config:
        from_attributes = True


class RankingsMeta(BaseModel):
    source: str
    total: int
    positions: List[str]
    tiers: List[str]
    teams: List[str]
    position_counts: dict
    tier_counts: dict


class RankingsImportResult(BaseModel):
    source: str
    imported: int
    updated: int
    total: int


class RankingSource(BaseModel):
    source: str
    count: int


class RankingsDeleteResult(BaseModel):
    source: str
    deleted: int


class RankingsRenameResult(BaseModel):
    old_source: str
    new_source: str
    count: int


# ---- Activity ----

class ActivityOut(BaseModel):
    id: int
    pipeline_entry_id: Optional[int]
    action: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    notes: Optional[str]
    created_at: Optional[datetime]
    prospect_name: Optional[str] = None
    client_name: Optional[str] = None

    class Config:
        from_attributes = True


# ---- Pipeline Summary ----

class PipelineSummary(BaseModel):
    total: int
    hot: int
    warm: int
    monitor: int
    pass_count: int
    unscored: int
    filtered: int = 0
    avg_matchmaker: Optional[float]
    avg_pmf: Optional[float]
    avg_rs: Optional[float]


# ---- Behavior Profiles ----

class BehaviorProfileCreate(BaseModel):
    sales_motion: Optional[str] = None
    partner_model: Optional[str] = None
    decision_speed: Optional[str] = None
    culture: Optional[str] = None
    customer_segment: Optional[str] = None
    partnership_history: Optional[str] = None
    notes: Optional[str] = None


class BehaviorProfileOut(BehaviorProfileCreate):
    id: int
    prospect_id: int
    assessed_by: str
    assessed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---- Intent Signals ----

class IntentSignalCreate(BaseModel):
    signal_type: str
    signal_detail: str
    signal_date: Optional[date] = None
    urgency: str = "moderate"
    relevance_note: Optional[str] = None
    source_url: Optional[str] = None


class IntentSignalOut(BaseModel):
    id: int
    prospect_id: int
    signal_type: str
    signal_detail: str
    signal_date: Optional[date]
    urgency: str
    relevance_note: Optional[str]
    source_url: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# ---- Identity Filters ----

class IdentityFilterCreate(BaseModel):
    allowed_business_models: Optional[str] = None  # JSON string
    allowed_stages: Optional[str] = None
    min_employees: Optional[int] = None
    max_employees: Optional[int] = None
    required_verticals: Optional[str] = None
    excluded_verticals: Optional[str] = None
    required_states: Optional[str] = None
    notes: Optional[str] = None


class IdentityFilterOut(BaseModel):
    id: int
    client_id: int
    allowed_business_models: Optional[str]
    allowed_stages: Optional[str]
    min_employees: Optional[int]
    max_employees: Optional[int]
    required_verticals: Optional[str]
    excluded_verticals: Optional[str]
    required_states: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True
