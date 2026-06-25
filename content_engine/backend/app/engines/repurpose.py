"""Content repurposing engine.

Takes one piece of content and transforms it into multiple target formats,
each adapted to its own best practices (not just summarized).
"""
from __future__ import annotations

from typing import Any

from ..ai.prompts import SYSTEM_GENERATOR, build_repurpose_prompt
from ..ai.provider import AIProvider

# Sensible default repurpose targets for a given source type.
DEFAULT_TARGETS = [
    "LinkedIn post", "Email newsletter", "5 short social posts",
    "Landing page section", "Sales email", "Website FAQ",
    "Short video script", "X/Twitter thread", "Executive summary",
]


def repurpose(*, provider: AIProvider, source_body: str, source_type: str,
              targets: list[str] | None, project: dict, brand: dict | None) -> list[dict[str, Any]]:
    targets = targets or DEFAULT_TARGETS
    prompt = build_repurpose_prompt(
        source_body=source_body, source_type=source_type, targets=targets,
        project=project, brand=brand,
    )
    data = provider.complete_json(SYSTEM_GENERATOR, prompt)
    outputs = data.get("outputs") if isinstance(data, dict) else None
    if isinstance(outputs, list) and outputs:
        return [{"format": o.get("format", "Output"), "content": o.get("content", "")}
                for o in outputs if isinstance(o, dict)]
    # Fallback: one completion per target.
    results = []
    for t in targets:
        text = provider.complete(SYSTEM_GENERATOR,
                                 f"Repurpose this {source_type} into a {t}:\n{source_body}",
                                 max_tokens=800)
        results.append({"format": t, "content": text})
    return results
