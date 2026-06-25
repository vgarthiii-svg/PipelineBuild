"""Research engine.

Produces a timestamped, source-cited research brief BEFORE drafting. It analyzes
trends, high-performing patterns, competitor themes, hooks, SEO/keyword
opportunities, search intent, related questions, market context, audience pain
points, and content gaps.

Provider strategy:
- If a real key + RESEARCH_PROVIDER=anthropic_web, ask the model to ground its
  brief in current knowledge and surface candidate sources.
- Otherwise the MockProvider returns a structured, clearly-labeled synthesized
  brief so the workflow always completes.

The engine NEVER copies viral content — the prompt instructs pattern synthesis.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..ai.prompts import SYSTEM_RESEARCHER, build_research_prompt
from ..ai.provider import AIProvider
from ..config import settings


def run_research(*, provider: AIProvider, project: dict, brand: dict | None) -> dict[str, Any]:
    prompt = build_research_prompt(project=project, brand=brand)
    data = provider.complete_json(SYSTEM_RESEARCHER, prompt)

    if not isinstance(data, dict) or data.get("_parse_error"):
        data = {}

    # Normalize list fields and guarantee presence.
    def lst(key):
        v = data.get(key)
        return v if isinstance(v, list) else []

    sources = data.get("sources") if isinstance(data.get("sources"), list) else []
    now = datetime.now(timezone.utc)
    norm_sources = []
    for s in sources:
        if not isinstance(s, dict):
            continue
        norm_sources.append({
            "title": s.get("title", "Source"),
            "url": s.get("url", ""),
            "snippet": s.get("snippet", ""),
            "source_type": s.get("source_type", "synthesized"),
            "retrieved_at": now.isoformat(),
        })
    if not norm_sources:
        norm_sources = [{
            "title": "Synthesized best-practice patterns",
            "url": "",
            "snippet": "No live web sources available; brief synthesized from "
                       "platform best practices and model knowledge.",
            "source_type": "synthesized",
            "retrieved_at": now.isoformat(),
        }]

    model_used = provider.name if settings.research_enabled else f"{provider.name} (synthesized)"

    return {
        "trends": lst("trends"),
        "high_performing_patterns": lst("high_performing_patterns"),
        "competitor_observations": lst("competitor_observations"),
        "audience_pain_points": lst("audience_pain_points"),
        "content_gaps": lst("content_gaps"),
        "common_hooks": lst("common_hooks"),
        "keywords": lst("keywords"),
        "related_questions": lst("related_questions"),
        "search_intent": data.get("search_intent", ""),
        "recommended_angle": data.get("recommended_angle", ""),
        "recommended_hook": data.get("recommended_hook", ""),
        "recommended_cta": data.get("recommended_cta", ""),
        "risks": data.get("risks", ""),
        "market_context": data.get("market_context", ""),
        "model_used": model_used,
        "generated_at": now,
        "sources": norm_sources,
    }
