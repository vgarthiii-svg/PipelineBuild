"""Pydantic request/response schemas for the API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    # protected_namespaces=() allows fields like `model_used` without warnings.
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


# --- Brand profiles ---------------------------------------------------------
class BrandIn(BaseModel):
    name: str
    company_name: str = ""
    website: str = ""
    industry: str = ""
    audience: str = ""
    products_services: str = ""
    brand_voice: str = ""
    words_to_use: list[str] = Field(default_factory=list)
    words_to_avoid: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    differentiators: str = ""
    proof_points: str = ""
    offers: str = ""
    compliance_rules: str = ""
    preferred_cta_language: str = ""
    style_preferences: dict[str, Any] = Field(default_factory=dict)
    approved_boilerplate: str = ""
    team_notes: str = ""


class BrandOut(ORM, BrandIn):
    id: int
    created_at: datetime
    updated_at: datetime


# --- Content projects -------------------------------------------------------
class ProjectIn(BaseModel):
    brand_id: int | None = None
    title: str = "Untitled"
    campaign: str = ""
    platform: str = ""
    content_type: str = ""
    objective: str = ""
    target_audience: str = ""
    business_goal: str = ""
    funnel_stage: str = ""
    tone: str = ""
    cta: str = ""
    length: str = "medium"
    keywords: list[str] = Field(default_factory=list)
    offer: str = ""
    industry: str = ""
    competitors: list[str] = Field(default_factory=list)
    geo_market: str = ""
    compliance: str = ""
    desired_outcome: str = ""
    status: str = "idea"


class ProjectOut(ORM, ProjectIn):
    id: int
    created_at: datetime
    updated_at: datetime


# --- Drafts / scores --------------------------------------------------------
class DraftOut(ORM):
    id: int
    project_id: int
    version: int
    title: str
    body: str
    structured: dict[str, Any]
    headline_options: list[Any]
    cta_options: list[Any]
    hook_options: list[Any]
    rationale: str
    posting_guidance: str
    repurposing_suggestions: list[Any]
    recommended_edits: list[Any]
    is_final: bool
    model_used: str
    created_at: datetime


class ScoreOut(ORM):
    id: int
    draft_id: int
    overall: int
    categories: dict[str, Any]
    summary: str
    created_at: datetime


class ResearchOut(ORM):
    id: int
    project_id: int
    trends: list[Any]
    high_performing_patterns: list[Any]
    competitor_observations: list[Any]
    audience_pain_points: list[Any]
    content_gaps: list[Any]
    common_hooks: list[Any]
    keywords: list[Any]
    related_questions: list[Any]
    search_intent: str
    recommended_angle: str
    recommended_hook: str
    recommended_cta: str
    risks: str
    market_context: str
    model_used: str
    generated_at: datetime


# --- Actions ----------------------------------------------------------------
class ReviseIn(BaseModel):
    action: str
    instruction: str = ""
    body: str | None = None  # if omitted, uses the draft's current body


class RepurposeIn(BaseModel):
    targets: list[str] | None = None
    body: str | None = None


class CalendarIn(BaseModel):
    title: str
    platform: str = ""
    scheduled_date: datetime
    status: str = "scheduled"
    notes: str = ""
    project_id: int | None = None
    draft_id: int | None = None


class TagIn(BaseModel):
    name: str
    color: str = "#6366f1"


class SnippetIn(BaseModel):
    kind: str
    label: str
    value: str = ""


class StyleRuleIn(BaseModel):
    name: str
    category: str = "clarity"
    rule: str
    detection: dict[str, Any] = Field(default_factory=dict)
    severity: str = "warning"
    brand_id: int | None = None
    enabled: bool = True


class SettingIn(BaseModel):
    key: str
    value: str
