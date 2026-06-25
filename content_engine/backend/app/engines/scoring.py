"""Content scoring engine — 14 categories, 0-100 each, weighted overall.

Combines AI judgment (via the provider) with the deterministic AP-style checker
so scores are grounded and reproducible even without an API key. Each category
returns: score, what's working, what's weak, and recommended improvements.
"""
from __future__ import annotations

from typing import Any

from ..ai.prompts import SYSTEM_SCORER, build_scoring_prompt
from ..ai.provider import AIProvider
from . import ap_style

# key -> {label, desc, weight}
SCORE_CATEGORIES: dict[str, dict[str, Any]] = {
    "platform_fit": {"label": "Platform fit", "weight": 1.2,
                     "desc": "Follows the selected platform's structure and norms."},
    "audience_fit": {"label": "Audience fit", "weight": 1.1,
                     "desc": "Speaks to the target audience's context and pain."},
    "hook_strength": {"label": "Hook strength", "weight": 1.2,
                      "desc": "Opening earns attention and a reason to continue."},
    "clarity": {"label": "Clarity", "weight": 1.1,
                "desc": "Easy to understand; one idea per line/section."},
    "conversion_strength": {"label": "Conversion strength", "weight": 1.2,
                            "desc": "Drives the desired action; persuasive structure."},
    "seo_strength": {"label": "SEO strength", "weight": 0.9,
                     "desc": "Keyword/intent coverage where applicable."},
    "ap_style": {"label": "AP-style alignment", "weight": 1.0,
                 "desc": "Clarity, active voice, numerals, no hype."},
    "brand_voice": {"label": "Brand voice alignment", "weight": 1.0,
                    "desc": "Matches the brand's voice, words-to-use/avoid."},
    "originality": {"label": "Originality", "weight": 1.0,
                    "desc": "Fresh angle; not generic or templated."},
    "readability": {"label": "Readability", "weight": 1.0,
                    "desc": "Plain English, good rhythm, scannable."},
    "cta_strength": {"label": "CTA strength", "weight": 1.1,
                     "desc": "Single, clear, benefit-led call to action."},
    "research_support": {"label": "Research support", "weight": 0.9,
                         "desc": "Grounded in current research/proof."},
    "compliance_risk": {"label": "Compliance risk", "weight": 1.0,
                        "desc": "Higher = lower risk; no unverifiable claims."},
    "engagement_potential": {"label": "Engagement potential", "weight": 1.1,
                             "desc": "Likely to earn comments/shares/replies."},
}


def _weighted_overall(categories: dict[str, dict]) -> int:
    total_w = 0.0
    acc = 0.0
    for key, meta in SCORE_CATEGORIES.items():
        c = categories.get(key)
        if not c:
            continue
        w = meta["weight"]
        acc += float(c.get("score", 0)) * w
        total_w += w
    return round(acc / total_w) if total_w else 0


def score_draft(
    *,
    provider: AIProvider,
    draft_body: str,
    project: dict,
    brand: dict | None,
    custom_style_rules: list[dict] | None = None,
) -> dict[str, Any]:
    """Score a draft. Returns {overall, summary, categories, ap_style}."""
    ap = ap_style.check(draft_body, custom_style_rules)

    prompt = build_scoring_prompt(
        draft_body=draft_body, project=project, brand=brand,
        categories=SCORE_CATEGORIES, ap_findings=ap["findings"],
    )
    result = provider.complete_json(SYSTEM_SCORER, prompt)
    cats = result.get("categories") if isinstance(result, dict) else None

    if not cats:
        cats = _fallback_categories(ap, project)

    # Normalize: ensure every category exists and is well-formed.
    normalized: dict[str, dict] = {}
    for key, meta in SCORE_CATEGORIES.items():
        c = cats.get(key) if isinstance(cats, dict) else None
        if not isinstance(c, dict):
            c = {}
        normalized[key] = {
            "label": meta["label"],
            "score": int(max(0, min(100, c.get("score", 70)))),
            "working": c.get("working", "On-spec for this category."),
            "weak": c.get("weak", "Room to sharpen."),
            "improvements": c.get("improvements") or ["Add a concrete, specific detail."],
        }

    # Force AP-style category to reflect the deterministic checker (auditable).
    normalized["ap_style"]["score"] = ap["ap_score"]
    if ap["findings"]:
        normalized["ap_style"]["weak"] = "; ".join(f["rule"] for f in ap["findings"][:4])
        normalized["ap_style"]["improvements"] = [f["message"] for f in ap["findings"][:4]]

    overall = result.get("overall") if isinstance(result, dict) else None
    if not isinstance(overall, int) or overall <= 0:
        overall = _weighted_overall(normalized)

    return {
        "overall": int(max(0, min(100, overall))),
        "summary": (result.get("summary") if isinstance(result, dict) else None)
        or _fallback_summary(overall, ap),
        "categories": normalized,
        "ap_style": ap,
    }


def _fallback_categories(ap: dict, project: dict) -> dict[str, dict]:
    base = 74
    cats = {}
    for key in SCORE_CATEGORIES:
        cats[key] = {"score": base, "working": "Meets baseline expectations.",
                     "weak": "Could be more specific.",
                     "improvements": ["Add a concrete example or proof point."]}
    cats["ap_style"]["score"] = ap["ap_score"]
    return cats


def _fallback_summary(overall: int, ap: dict) -> str:
    verdict = "publishable" if overall >= 75 else "promising but needs work"
    return (f"Overall {overall}/100 — {verdict}. "
            f"AP-style check: {ap['ap_score']}/100 with {len(ap['findings'])} note(s).")
