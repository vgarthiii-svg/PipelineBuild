"""Modular prompt template system.

Each function returns a self-contained, composable prompt MODULE. The engines
assemble the modules they need (brand + platform + content-type + audience +
research + AP-style + SEO + CTA + compliance) into one prompt. This guarantees
output is always grounded in the user's inputs — never generic.
"""
from __future__ import annotations

from typing import Any

SYSTEM_GENERATOR = (
    "You are a senior content strategist and conversion copywriter who also "
    "thinks like a journalist. You write original, platform-native content that "
    "follows best practices, AP-style journalistic principles, brand voice, SEO "
    "rules, and conversion strategy. You never produce generic filler. You ground "
    "every choice in the supplied brand profile, platform rules, audience, and "
    "current research. You never plagiarize viral content — you learn from its "
    "patterns and create something original."
)

SYSTEM_SCORER = (
    "You are a rigorous content editor and growth analyst. You score marketing "
    "content honestly across defined categories, explain what works and what is "
    "weak, and give concrete, actionable improvements. You are not a cheerleader; "
    "a 100 is rare. You penalize hype, vagueness, weak hooks, and unsupported claims."
)

SYSTEM_RESEARCHER = (
    "You are a market and content researcher. You identify current trends, "
    "high-performing patterns, hooks, audience pain points, SEO opportunities, "
    "and content gaps. You synthesize patterns rather than copying. You always "
    "cite sources and note the recency and confidence of your findings."
)


# --------------------------------------------------------------------------- #
# Context modules
# --------------------------------------------------------------------------- #
def brand_module(brand: dict[str, Any] | None) -> str:
    if not brand:
        return "BRAND CONTEXT: (none provided — keep voice neutral-professional)."
    lines = ["BRAND CONTEXT:"]
    fields = [
        ("Company", brand.get("company_name")),
        ("Website", brand.get("website")),
        ("Industry", brand.get("industry")),
        ("Audience", brand.get("audience")),
        ("Products/Services", brand.get("products_services")),
        ("Brand voice", brand.get("brand_voice")),
        ("Differentiators", brand.get("differentiators")),
        ("Proof points", brand.get("proof_points")),
        ("Offers", brand.get("offers")),
        ("Preferred CTA language", brand.get("preferred_cta_language")),
        ("Approved boilerplate", brand.get("approved_boilerplate")),
        ("Compliance rules", brand.get("compliance_rules")),
    ]
    for label, val in fields:
        if val:
            lines.append(f"- {label}: {val}")
    if brand.get("words_to_use"):
        lines.append(f"- Words to USE: {', '.join(brand['words_to_use'])}")
    if brand.get("words_to_avoid"):
        lines.append(f"- Words to AVOID: {', '.join(brand['words_to_avoid'])}")
    if brand.get("competitors"):
        lines.append(f"- Competitors: {', '.join(brand['competitors'])}")
    return "\n".join(lines)


def platform_module(rule: dict[str, Any] | None, platform: str, content_type: str) -> str:
    if not rule:
        return f"PLATFORM: {platform} / {content_type}. Follow current best practices for this surface."
    lines = [f"PLATFORM RULES — {rule.get('label', platform)} ({platform}/{content_type}):"]
    if rule.get("structure"):
        lines.append("Required structure (in order): " + " -> ".join(rule["structure"]))
    if rule.get("best_practices"):
        lines.append("Best practices:")
        lines += [f"  - {bp}" for bp in rule["best_practices"]]
    if rule.get("constraints"):
        lines.append(f"Constraints: {rule['constraints']}")
    return "\n".join(lines)


def audience_module(project: dict[str, Any]) -> str:
    parts = [
        "AUDIENCE & GOAL:",
        f"- Target audience: {project.get('target_audience') or 'general professional'}",
        f"- Business goal: {project.get('business_goal') or 'awareness'}",
        f"- Funnel stage: {project.get('funnel_stage') or 'TOFU'}",
        f"- Desired outcome: {project.get('desired_outcome') or 'engagement'}",
        f"- Geographic market: {project.get('geo_market') or 'global'}",
        f"- Tone: {project.get('tone') or 'professional'}",
    ]
    return "\n".join(parts)


def research_module(brief: dict[str, Any] | None) -> str:
    if not brief:
        return "RESEARCH: (not yet run — rely on best practices)."
    lines = ["CURRENT RESEARCH FINDINGS (ground the content in these):"]
    for key in ["trends", "high_performing_patterns", "common_hooks", "audience_pain_points", "content_gaps"]:
        vals = brief.get(key)
        if vals:
            lines.append(f"- {key.replace('_', ' ').title()}: " + "; ".join(vals[:5]))
    if brief.get("recommended_angle"):
        lines.append(f"- Recommended angle: {brief['recommended_angle']}")
    if brief.get("recommended_hook"):
        lines.append(f"- Recommended hook: {brief['recommended_hook']}")
    if brief.get("keywords"):
        lines.append(f"- Keywords: {', '.join(brief['keywords'][:10])}")
    return "\n".join(lines)


AP_STYLE_MODULE = (
    "AP-STYLE / JOURNALISTIC PRINCIPLES (apply, do not quote any stylebook):\n"
    "- Prefer clarity, concision, and active voice.\n"
    "- Spell out numbers one through nine; use figures for 10 and above.\n"
    "- Use sentence case for headlines unless brand dictates otherwise; avoid ALL CAPS.\n"
    "- Attribute claims clearly; avoid weasel words and unsupported superlatives.\n"
    "- Cut hype, fluff, and jargon; write in plain English.\n"
    "- Use the serial-comma policy consistently per the brand style preference.\n"
    "- Format dates/times consistently; avoid ambiguous abbreviations.\n"
    "- No exaggerated or unverifiable claims without a cited proof point."
)


def seo_module(project: dict[str, Any]) -> str:
    kws = project.get("keywords") or []
    if not kws and not project.get("content_type") in ("blog", "website", "landing", "brief"):
        return ""
    return (
        "SEO RULES:\n"
        f"- Primary/secondary keywords to work in naturally: {', '.join(kws) or '(infer 3-5)'}\n"
        "- Match search intent; answer the core question early.\n"
        "- Produce an SEO title (<=60 chars) and meta description (<=155 chars) when relevant.\n"
        "- Suggest H1/H2/H3 structure, internal link ideas, and an FAQ where it fits.\n"
        "- Never keyword-stuff; readability beats density."
    )


def cta_module(project: dict[str, Any], brand: dict[str, Any] | None) -> str:
    preferred = (brand or {}).get("preferred_cta_language", "")
    return (
        "CTA RULES:\n"
        f"- Primary CTA: {project.get('cta') or 'drive the desired outcome'}\n"
        f"- Preferred CTA language: {preferred or '(use natural, benefit-led phrasing)'}\n"
        "- One primary CTA. Make the benefit of acting explicit. Offer 2-3 CTA variants."
    )


def compliance_module(project: dict[str, Any], brand: dict[str, Any] | None) -> str:
    notes = project.get("compliance") or (brand or {}).get("compliance_rules") or ""
    if not notes:
        return "COMPLIANCE: standard — no unverifiable claims, no guarantees of results."
    return f"COMPLIANCE CONSTRAINTS (must honor): {notes}"


# --------------------------------------------------------------------------- #
# Task prompts
# --------------------------------------------------------------------------- #
def build_generation_prompt(*, project: dict, brand: dict | None, rule: dict | None,
                            brief: dict | None) -> str:
    modules = [
        brand_module(brand),
        platform_module(rule, project.get("platform", ""), project.get("content_type", "")),
        audience_module(project),
        research_module(brief),
        AP_STYLE_MODULE,
        seo_module(project),
        cta_module(project, brand),
        compliance_module(project, brand),
    ]
    context = "\n\n".join(m for m in modules if m)
    length = project.get("length", "medium")
    return f"""{context}

TASK: Generate a first-draft {project.get('content_type','post')} for {project.get('platform','the platform')}.
objective: {project.get('objective','')}
offer: {project.get('offer','')}
length: {length}

Return a single JSON object with these keys:
- "title": short working title
- "body": the full draft as ready-to-publish text (use the required structure)
- "structured": object with "sections": [{{"name","text"}}] mirroring the platform structure
- "headline_options": 3-5 alternative headlines/hooks
- "cta_options": 2-3 CTA variants
- "hook_options": 2-3 opening hook variants
- "rationale": why this draft will perform (tie to research + best practices)
- "posting_guidance": platform-specific timing/format tips
- "repurposing_suggestions": 3-5 formats this could become
- "recommended_edits": [{{"area","suggestion"}}] for pushing the score higher

Make it original, specific to the inputs, and free of generic filler."""


def build_research_prompt(*, project: dict, brand: dict | None) -> str:
    topic = project.get("objective") or project.get("offer") or project.get("content_type")
    return f"""{SYSTEM_RESEARCHER}

Research the following so we can create original, high-performing content.
topic: {topic}
platform: {project.get('platform')}
content_type: {project.get('content_type')}
industry: {project.get('industry') or (brand or {}).get('industry','')}
audience: {project.get('target_audience')}
competitors: {', '.join(project.get('competitors') or (brand or {}).get('competitors', []))}
geo_market: {project.get('geo_market')}

Produce a research brief as a single JSON object with keys:
trends, high_performing_patterns, competitor_observations, audience_pain_points,
content_gaps, common_hooks, keywords, related_questions, search_intent,
recommended_angle, recommended_hook, recommended_cta, risks, market_context,
and "sources": [{{"title","url","snippet","source_type"}}].

Synthesize PATTERNS — do not copy any specific post. Note recency and confidence."""


def build_scoring_prompt(*, draft_body: str, project: dict, brand: dict | None,
                         categories: dict, ap_findings: list | None = None) -> str:
    cat_list = "\n".join(f'- {k}: {v["label"]} — {v["desc"]}' for k, v in categories.items())
    ap_note = ""
    if ap_findings:
        ap_note = "\nDeterministic AP-style checker already flagged: " + "; ".join(
            f"{f['rule']} ({f['severity']})" for f in ap_findings[:10])
    return f"""{SYSTEM_SCORER}

Score the following content (a scorecard) across these categories (0-100 each):
{cat_list}

Context — platform: {project.get('platform')}, type: {project.get('content_type')},
audience: {project.get('target_audience')}, goal: {project.get('business_goal')},
brand voice: {(brand or {}).get('brand_voice','neutral')}.{ap_note}

CONTENT:
\"\"\"{draft_body}\"\"\"

Return a single JSON object:
{{"overall": <weighted 0-100 int>,
  "summary": "<2-3 sentence verdict>",
  "categories": {{ "<key>": {{"score": int, "working": str, "weak": str,
                              "improvements": [str, ...]}} }} }}
Use the exact category keys provided."""


def build_revision_prompt(*, body: str, action: str, instruction: str,
                          project: dict, brand: dict | None) -> str:
    action_map = {
        "rewrite": "Rewrite for higher impact while keeping the core message.",
        "shorten": "Cut length by ~40% with no loss of meaning; tighten every line.",
        "expand": "Expand with concrete detail, examples, and proof — no filler.",
        "professional": "Make it more polished and professional.",
        "conversational": "Make it warmer and more conversational, still credible.",
        "direct": "Make it more direct and punchy; remove hedging.",
        "add_stats": "Weave in 2-3 relevant, plausible statistics (mark any that need a real source).",
        "add_cta": "Strengthen and clarify the call to action.",
        "remove_fluff": "Remove hype, fluff, and filler; keep only what earns its place.",
        "ap_style": "Edit to AP-style journalistic principles (clarity, active voice, numerals, no hype).",
        "variations": "Produce 3 distinct variations of this content.",
    }
    directive = action_map.get(action, instruction or "Improve the content.")
    extra = f"\nAdditional instruction: {instruction}" if instruction else ""
    return f"""{SYSTEM_GENERATOR}

{brand_module(brand)}
{AP_STYLE_MODULE if action == 'ap_style' else ''}

REVISION TASK: {directive}{extra}
Keep it on-brand and platform-appropriate ({project.get('platform')}/{project.get('content_type')}).

CURRENT CONTENT:
\"\"\"{body}\"\"\"

Return only the revised content as plain text (or, for "variations", separate
each variation with a line of '---')."""


def build_repurpose_prompt(*, source_body: str, source_type: str, targets: list[str],
                           project: dict, brand: dict | None) -> str:
    return f"""{SYSTEM_GENERATOR}

{brand_module(brand)}

REPURPOSE TASK: Transform the following {source_type} into each target format.
Keep the core message; adapt structure, length, and tone to each format's best
practices. Make each output ready to publish — not a summary of the original.

Target formats: {', '.join(targets)}

SOURCE CONTENT:
\"\"\"{source_body}\"\"\"

Return a single JSON object: {{"outputs": [{{"format": str, "content": str}}, ...]}}"""
