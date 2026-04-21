from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, Float, Date, DateTime, ForeignKey, UniqueConstraint
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
    profile_json = Column(Text)  # Full company profile as JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    criteria = relationship("ScoringCriterion", back_populates="client", cascade="all, delete-orphan")
    pipeline_entries = relationship("PipelineEntry", back_populates="client")


class ScoringCriterion(Base):
    __tablename__ = "scoring_criteria"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    why_it_matters = Column(Text)
    weight = Column(Integer, default=5)  # 1-10
    sort_order = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="criteria")
    criterion_scores = relationship("CriterionScore", back_populates="criterion")


class Prospect(Base):
    __tablename__ = "prospects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String)  # "Regional Carrier", "National Brokerage", etc.
    website = Column(String)
    domain = Column(String)
    alternate_domains = Column(Text)  # JSON array
    hq_city = Column(String)
    hq_state = Column(String)
    employees = Column(Integer)
    revenue = Column(String)
    description = Column(Text)
    decision_makers_json = Column(Text)  # JSON array of {name, title, email, source}
    enrichment_source = Column(String)
    enrichment_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pipeline_entries = relationship("PipelineEntry", back_populates="prospect")
    relationships = relationship("Relationship", back_populates="prospect")
    scans = relationship("RelationshipScan", back_populates="prospect")


class PipelineEntry(Base):
    __tablename__ = "pipeline_entries"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    prospect_id = Column(Integer, ForeignKey("prospects.id"), nullable=False)
    source = Column(String)
    source_date = Column(Date)
    source_priority = Column(String)  # "first-mentioned", "standard"
    tier = Column(String, default="unscored")
    pmf_score = Column(Float)
    relationship_score = Column(Integer, default=0)  # 0-5
    matchmaker_score = Column(Float)
    pmf_weight = Column(Float, default=0.6)
    rs_weight = Column(Float, default=0.4)
    status = Column(String, default="new")
    next_action = Column(Text)
    notes = Column(Text)
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
    score = Column(Integer, default=0)  # 0-5
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
    score = Column(Integer, default=0)  # 0-5
    context = Column(Text)
    source = Column(String)  # "gmail", "hubspot", "calendar", "conference", "manual"
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
    gmail_details = Column(Text)  # JSON
    hubspot_hits = Column(Integer, default=0)
    hubspot_details = Column(Text)  # JSON
    calendar_hits = Column(Integer, default=0)
    calendar_details = Column(Text)  # JSON
    conference_hits = Column(Integer, default=0)
    conference_details = Column(Text)  # JSON
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
    talking_points = Column(Text)  # JSON array
    value_prop_prospect = Column(Text)
    value_prop_client = Column(Text)
    mutual_connections = Column(Text)  # JSON array
    objections_json = Column(Text)  # JSON array of {objection, response}
    status = Column(String, default="draft")
    sent_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    pipeline_entry = relationship("PipelineEntry", back_populates="intro_packages")


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_entry_id = Column(Integer, ForeignKey("pipeline_entries.id"))
    action = Column(String)  # "scored", "relationship_updated", "intro_sent", etc.
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
