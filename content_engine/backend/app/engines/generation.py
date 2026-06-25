"""Draft generation & revision engine.

Assembles the modular prompt (brand + platform + audience + research + AP-style +
SEO + CTA + compliance) and asks the provider for a structured draft. Revision
applies named editor actions (rewrite/shorten/expand/ap_style/etc.).
"""
from __future__ import annotations

from typing import Any

from ..ai.prompts import (
    SYSTEM_GENERATOR,
    build_generation_prompt,
    build_revision_prompt,
)
from ..ai.provider import AIProvider


def generate_draft(*, provider: AIProvider, project: dict, brand: dict | None,
                   rule: dict | None, brief: dict | None) -> dict[str, Any]:
    prompt = build_generation_prompt(project=project, brand=brand, rule=rule, brief=brief)
    data = provider.complete_json(SYSTEM_GENERATOR, prompt)

    if not isinstance(data, dict) or data.get("_parse_error"):
        # Degrade to a plain completion so the user still gets a draft.
        body = provider.complete(SYSTEM_GENERATOR, prompt, max_tokens=2000)
        data = {"title": project.get("title", "Draft"), "body": body}

    def lst(key):
        v = data.get(key)
        return v if isinstance(v, list) else []

    return {
        "title": data.get("title") or project.get("title", "Draft"),
        "body": data.get("body", ""),
        "structured": data.get("structured") if isinstance(data.get("structured"), dict) else {},
        "headline_options": lst("headline_options"),
        "cta_options": lst("cta_options"),
        "hook_options": lst("hook_options"),
        "rationale": data.get("rationale", ""),
        "posting_guidance": data.get("posting_guidance", ""),
        "repurposing_suggestions": lst("repurposing_suggestions"),
        "recommended_edits": lst("recommended_edits"),
        "model_used": provider.name,
    }


def revise_draft(*, provider: AIProvider, body: str, action: str, instruction: str,
                 project: dict, brand: dict | None) -> str:
    prompt = build_revision_prompt(
        body=body, action=action, instruction=instruction, project=project, brand=brand,
    )
    return provider.complete(SYSTEM_GENERATOR, prompt, max_tokens=2200).strip()
