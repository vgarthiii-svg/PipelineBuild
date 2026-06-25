"""Metadata endpoints that drive the wizard dropdowns and scorecard UI."""
from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..engines.platform_rules import CONTENT_TYPES, PLATFORMS
from ..engines.scoring import SCORE_CATEGORIES

router = APIRouter(prefix="/api/meta", tags=["meta"])

FUNNEL_STAGES = ["Awareness (TOFU)", "Consideration (MOFU)", "Decision (BOFU)", "Retention", "Advocacy"]
TONES = ["Professional", "Conversational", "Authoritative", "Bold", "Friendly",
         "Witty", "Empathetic", "Inspirational", "Data-driven", "Minimal"]
BUSINESS_GOALS = ["Brand awareness", "Lead generation", "Demand generation", "Engagement",
                  "Conversions/Sales", "Retention", "Thought leadership", "Recruiting"]
LENGTHS = ["short", "medium", "long"]
STATUSES = ["idea", "researching", "drafted", "needs_review", "approved",
            "scheduled", "published", "archived"]
EDITOR_ACTIONS = [
    {"action": "rewrite", "label": "Rewrite"},
    {"action": "shorten", "label": "Shorten"},
    {"action": "expand", "label": "Expand"},
    {"action": "professional", "label": "More professional"},
    {"action": "conversational", "label": "More conversational"},
    {"action": "direct", "label": "More direct"},
    {"action": "add_stats", "label": "Add statistics"},
    {"action": "add_cta", "label": "Add/strengthen CTA"},
    {"action": "remove_fluff", "label": "Remove fluff"},
    {"action": "ap_style", "label": "Convert to AP style"},
    {"action": "variations", "label": "Generate variations"},
]


@router.get("")
def meta() -> dict:
    return {
        "content_types": [{"value": v, "label": l} for v, l in CONTENT_TYPES],
        "platforms": PLATFORMS,
        "funnel_stages": FUNNEL_STAGES,
        "tones": TONES,
        "business_goals": BUSINESS_GOALS,
        "lengths": LENGTHS,
        "statuses": STATUSES,
        "editor_actions": EDITOR_ACTIONS,
        "score_categories": [{"key": k, "label": v["label"], "desc": v["desc"]}
                             for k, v in SCORE_CATEGORIES.items()],
        "ai_enabled": settings.ai_enabled,
        "research_enabled": settings.research_enabled,
        "ai_provider": settings.ai_provider,
    }
