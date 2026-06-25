"""Unit tests for the core engines (run with the deterministic mock provider)."""
from __future__ import annotations

from app.ai.provider import MockProvider
from app.engines import ap_style, generation, repurpose, research, scoring

PROJECT = {
    "title": "Launch post", "platform": "LinkedIn", "content_type": "linkedin",
    "objective": "announce our new analytics feature", "target_audience": "RevOps leaders",
    "business_goal": "Lead generation", "funnel_stage": "MOFU", "tone": "Professional",
    "cta": "Book a demo", "length": "medium", "keywords": ["revops", "analytics"],
    "offer": "free trial", "industry": "SaaS", "competitors": ["Acme"],
    "geo_market": "US", "compliance": "", "desired_outcome": "demo bookings",
}
BRAND = {"company_name": "Northstar", "brand_voice": "confident, plain-spoken",
         "words_to_avoid": ["synergy"], "words_to_use": ["clarity"], "competitors": ["Acme"]}


def test_ap_style_flags_hype_and_scores():
    res = ap_style.check("This revolutionary, world-class, game-changer tool is the best!")
    assert res["ap_score"] < 100
    assert any(f["category"] == "hype" for f in res["findings"])


def test_ap_style_clean_text_scores_high():
    res = ap_style.check("We shipped a tool. It helps teams report faster. Try it today.")
    assert res["ap_score"] >= 80


def test_generate_draft_returns_full_structure():
    draft = generation.generate_draft(provider=MockProvider(), project=PROJECT,
                                      brand=BRAND, rule=None, brief=None)
    assert draft["body"]
    assert len(draft["headline_options"]) >= 1
    assert "model_used" in draft


def test_research_brief_has_sources_and_timestamp():
    brief = research.run_research(provider=MockProvider(), project=PROJECT, brand=BRAND)
    assert brief["sources"]
    assert brief["generated_at"]
    assert brief["keywords"]


def test_scoring_returns_14_categories():
    result = scoring.score_draft(provider=MockProvider(),
                                 draft_body="A clear, concise draft with a hook and one CTA.",
                                 project=PROJECT, brand=BRAND)
    assert set(result["categories"].keys()) == set(scoring.SCORE_CATEGORIES.keys())
    assert 0 <= result["overall"] <= 100
    # AP-style category is driven by the deterministic checker.
    assert result["categories"]["ap_style"]["score"] == result["ap_style"]["ap_score"]


def test_repurpose_produces_outputs():
    outputs = repurpose.repurpose(provider=MockProvider(), source_body="A blog post about X.",
                                  source_type="blog", targets=["LinkedIn post", "Email newsletter"],
                                  project=PROJECT, brand=BRAND)
    assert len(outputs) >= 2
    assert all("format" in o and "content" in o for o in outputs)
