"""SQLAlchemy ORM models — the durable data structure of the engine.

Tables map 1:1 to the deliverable's database structure requirement:
users, brand_profiles, content_projects, content_drafts, research_briefs,
research_sources, scores, revision_history, platform_rules, style_guide_rules,
content_calendar, export_history, tags (+ saved snippets and app settings).

JSON columns are used for flexible, list/dict-shaped fields. The SQLAlchemy
JSON type is portable across SQLite and PostgreSQL.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Many-to-many: drafts <-> tags -----------------------------------------
content_tags = Table(
    "content_tags",
    Base.metadata,
    Column("draft_id", ForeignKey("content_drafts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    brands: Mapped[list["BrandProfile"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    projects: Mapped[list["ContentProject"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class BrandProfile(Base):
    __tablename__ = "brand_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(255))
    company_name: Mapped[str] = mapped_column(String(255), default="")
    website: Mapped[str] = mapped_column(String(512), default="")
    industry: Mapped[str] = mapped_column(String(255), default="")
    audience: Mapped[str] = mapped_column(Text, default="")
    products_services: Mapped[str] = mapped_column(Text, default="")
    brand_voice: Mapped[str] = mapped_column(Text, default="")
    words_to_use: Mapped[list] = mapped_column(JSON, default=list)
    words_to_avoid: Mapped[list] = mapped_column(JSON, default=list)
    competitors: Mapped[list] = mapped_column(JSON, default=list)
    differentiators: Mapped[str] = mapped_column(Text, default="")
    proof_points: Mapped[str] = mapped_column(Text, default="")
    offers: Mapped[str] = mapped_column(Text, default="")
    compliance_rules: Mapped[str] = mapped_column(Text, default="")
    preferred_cta_language: Mapped[str] = mapped_column(Text, default="")
    style_preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    approved_boilerplate: Mapped[str] = mapped_column(Text, default="")
    team_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    user: Mapped[User] = relationship(back_populates="brands")
    projects: Mapped[list["ContentProject"]] = relationship(back_populates="brand")


class ContentProject(Base):
    """A single content request/campaign — captures all wizard inputs."""

    __tablename__ = "content_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brand_profiles.id", ondelete="SET NULL"), nullable=True)

    title: Mapped[str] = mapped_column(String(512), default="Untitled")
    campaign: Mapped[str] = mapped_column(String(255), default="")
    platform: Mapped[str] = mapped_column(String(64), default="")
    content_type: Mapped[str] = mapped_column(String(64), default="")
    objective: Mapped[str] = mapped_column(Text, default="")
    target_audience: Mapped[str] = mapped_column(Text, default="")
    business_goal: Mapped[str] = mapped_column(String(255), default="")
    funnel_stage: Mapped[str] = mapped_column(String(64), default="")
    tone: Mapped[str] = mapped_column(String(128), default="")
    cta: Mapped[str] = mapped_column(Text, default="")
    length: Mapped[str] = mapped_column(String(64), default="medium")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    offer: Mapped[str] = mapped_column(Text, default="")
    industry: Mapped[str] = mapped_column(String(255), default="")
    competitors: Mapped[list] = mapped_column(JSON, default=list)
    geo_market: Mapped[str] = mapped_column(String(255), default="")
    compliance: Mapped[str] = mapped_column(Text, default="")
    desired_outcome: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[str] = mapped_column(String(32), default="idea", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    user: Mapped[User] = relationship(back_populates="projects")
    brand: Mapped[BrandProfile | None] = relationship(back_populates="projects")
    briefs: Mapped[list["ResearchBrief"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    drafts: Mapped[list["ContentDraft"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ResearchBrief(Base):
    __tablename__ = "research_briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("content_projects.id", ondelete="CASCADE"), index=True)

    trends: Mapped[list] = mapped_column(JSON, default=list)
    high_performing_patterns: Mapped[list] = mapped_column(JSON, default=list)
    competitor_observations: Mapped[list] = mapped_column(JSON, default=list)
    audience_pain_points: Mapped[list] = mapped_column(JSON, default=list)
    content_gaps: Mapped[list] = mapped_column(JSON, default=list)
    common_hooks: Mapped[list] = mapped_column(JSON, default=list)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    related_questions: Mapped[list] = mapped_column(JSON, default=list)
    search_intent: Mapped[str] = mapped_column(Text, default="")
    recommended_angle: Mapped[str] = mapped_column(Text, default="")
    recommended_hook: Mapped[str] = mapped_column(Text, default="")
    recommended_cta: Mapped[str] = mapped_column(Text, default="")
    risks: Mapped[str] = mapped_column(Text, default="")
    market_context: Mapped[str] = mapped_column(Text, default="")
    model_used: Mapped[str] = mapped_column(String(128), default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped[ContentProject] = relationship(back_populates="briefs")
    sources: Mapped[list["ResearchSource"]] = relationship(back_populates="brief", cascade="all, delete-orphan")


class ResearchSource(Base):
    __tablename__ = "research_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brief_id: Mapped[int] = mapped_column(ForeignKey("research_briefs.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(512), default="")
    url: Mapped[str] = mapped_column(String(1024), default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(64), default="web")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    brief: Mapped[ResearchBrief] = relationship(back_populates="sources")


class ContentDraft(Base):
    __tablename__ = "content_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("content_projects.id", ondelete="CASCADE"), index=True)

    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(512), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    structured: Mapped[dict] = mapped_column(JSON, default=dict)  # platform-specific sections
    headline_options: Mapped[list] = mapped_column(JSON, default=list)
    cta_options: Mapped[list] = mapped_column(JSON, default=list)
    hook_options: Mapped[list] = mapped_column(JSON, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    posting_guidance: Mapped[str] = mapped_column(Text, default="")
    repurposing_suggestions: Mapped[list] = mapped_column(JSON, default=list)
    recommended_edits: Mapped[list] = mapped_column(JSON, default=list)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    model_used: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped[ContentProject] = relationship(back_populates="drafts")
    scores: Mapped[list["Score"]] = relationship(back_populates="draft", cascade="all, delete-orphan")
    revisions: Mapped[list["RevisionHistory"]] = relationship(back_populates="draft", cascade="all, delete-orphan")
    tags: Mapped[list["Tag"]] = relationship(secondary=content_tags, back_populates="drafts")


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("content_drafts.id", ondelete="CASCADE"), index=True)

    overall: Mapped[int] = mapped_column(Integer, default=0)
    # categories: {key: {"score": int, "working": str, "weak": str, "improvements": [..]}}
    categories: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    draft: Mapped[ContentDraft] = relationship(back_populates="scores")


class RevisionHistory(Base):
    __tablename__ = "revision_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("content_drafts.id", ondelete="CASCADE"), index=True)

    action: Mapped[str] = mapped_column(String(64))  # rewrite, shorten, expand, ap_style, ...
    instruction: Mapped[str] = mapped_column(Text, default="")
    before_text: Mapped[str] = mapped_column(Text, default="")
    after_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    draft: Mapped[ContentDraft] = relationship(back_populates="revisions")


class PlatformRule(Base):
    __tablename__ = "platform_rules"
    __table_args__ = (UniqueConstraint("platform", "content_type", name="uq_platform_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(64), index=True)
    content_type: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(255), default="")
    structure: Mapped[list] = mapped_column(JSON, default=list)  # ordered sections
    best_practices: Mapped[list] = mapped_column(JSON, default=list)
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)  # length, hashtags, emoji policy
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class StyleGuideRule(Base):
    __tablename__ = "style_guide_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=True)

    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64), default="clarity")
    rule: Mapped[str] = mapped_column(Text)
    # detection: {"type": "regex"|"phrase"|"heuristic", "pattern": str, "message": str}
    detection: Mapped[dict] = mapped_column(JSON, default=dict)
    severity: Mapped[str] = mapped_column(String(16), default="warning")  # info|warning|error
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ContentCalendarEntry(Base):
    __tablename__ = "content_calendar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("content_projects.id", ondelete="SET NULL"), nullable=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("content_drafts.id", ondelete="SET NULL"), nullable=True)

    title: Mapped[str] = mapped_column(String(512))
    platform: Mapped[str] = mapped_column(String(64), default="")
    scheduled_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ExportHistory(Base):
    __tablename__ = "export_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("content_drafts.id", ondelete="CASCADE"), index=True)
    fmt: Mapped[str] = mapped_column(String(16))
    filename: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    color: Mapped[str] = mapped_column(String(16), default="#6366f1")

    drafts: Mapped[list[ContentDraft]] = relationship(secondary=content_tags, back_populates="tags")


class SavedSnippet(Base):
    """Reusable CTAs, offers, audiences, compliance notes for Settings/Admin."""

    __tablename__ = "saved_snippets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # cta|offer|audience|compliance
    label: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AppSetting(Base):
    """Per-user key/value settings (default export format, provider prefs)."""

    __tablename__ = "app_settings"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_setting"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(Text, default="")
