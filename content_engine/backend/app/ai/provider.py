"""Modular AI provider abstraction.

The rest of the app depends only on the `AIProvider` interface, never on a
specific vendor. Swap providers by changing AI_PROVIDER in the environment.
A deterministic MockProvider guarantees the app runs (and tests pass) with no
API key, returning structured, on-spec output rather than failing.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ..config import settings


class AIProvider:
    """Interface every provider implements."""

    name: str = "base"

    def complete(self, system: str, prompt: str, max_tokens: int = 2000, temperature: float = 0.7) -> str:
        raise NotImplementedError

    def complete_json(self, system: str, prompt: str, max_tokens: int = 3000) -> dict[str, Any]:
        """Return parsed JSON. Implementations should instruct the model to
        emit a single JSON object; this base helper extracts it defensively."""
        raw = self.complete(system + "\n\nRespond with a single valid JSON object and nothing else.",
                            prompt, max_tokens=max_tokens, temperature=0.4)
        return _extract_json(raw)


def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction from a model response."""
    text = text.strip()
    # Strip code fences if present.
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Grab the outermost braces.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return {"_raw": text, "_parse_error": True}


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(self) -> None:
        import anthropic  # imported lazily so the app loads without the dep configured

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    def complete(self, system: str, prompt: str, max_tokens: int = 2000, temperature: float = 0.7) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")


class MockProvider(AIProvider):
    """Deterministic, dependency-free provider.

    Produces structured, on-brand-looking output derived from the prompt so the
    full workflow (generate -> score -> revise -> repurpose) works offline.
    It is intentionally template-driven; real quality comes from AnthropicProvider.
    """

    name = "mock"

    def complete(self, system: str, prompt: str, max_tokens: int = 2000, temperature: float = 0.7) -> str:
        return (
            "[Mock AI output — set ANTHROPIC_API_KEY for live generation]\n\n"
            + _mock_prose_from_prompt(prompt)
        )

    def complete_json(self, system: str, prompt: str, max_tokens: int = 3000) -> dict[str, Any]:
        # The engines call provider.complete_json with a hint of what they need.
        # We branch on lightweight markers embedded by the prompt templates.
        low = prompt.lower()
        if "score the following" in low or "scorecard" in low:
            return _mock_scorecard()
        if "research brief" in low or "research the following" in low:
            return _mock_research(prompt)
        if "repurpose" in low:
            return _mock_repurpose(prompt)
        return _mock_draft(prompt)


# --------------------------------------------------------------------------- #
# Mock content helpers
# --------------------------------------------------------------------------- #
def _ctx(prompt: str, key: str, default: str = "") -> str:
    m = re.search(rf"{re.escape(key)}\s*[:=]\s*(.+)", prompt, re.IGNORECASE)
    return m.group(1).strip().splitlines()[0] if m else default


def _mock_prose_from_prompt(prompt: str) -> str:
    topic = _ctx(prompt, "objective") or _ctx(prompt, "topic") or "your initiative"
    audience = _ctx(prompt, "audience") or "your audience"
    return (
        f"Here is the opening hook that earns attention from {audience}.\n\n"
        f"Most teams approach {topic} backwards. Here's the shift that changes outcomes.\n\n"
        "1) Name the real problem.\n2) Show the simpler path.\n3) Make the next step obvious.\n\n"
        "If this resonates, the call to action goes here."
    )


def _mock_draft(prompt: str) -> dict[str, Any]:
    topic = _ctx(prompt, "objective") or _ctx(prompt, "topic") or "this initiative"
    audience = _ctx(prompt, "audience") or "decision-makers"
    cta = _ctx(prompt, "cta") or "Book a call"
    return {
        "title": f"{topic.title()} — draft",
        "body": _mock_prose_from_prompt(prompt),
        "structured": {"sections": [{"name": "Hook", "text": "Attention-earning opener."},
                                    {"name": "Body", "text": "Value, proof, structure."},
                                    {"name": "CTA", "text": cta}]},
        "headline_options": [
            f"The honest take on {topic}",
            f"What {audience} get wrong about {topic}",
            f"A simpler path to {topic}",
        ],
        "cta_options": [cta, f"{cta} this week", "See how it works"],
        "hook_options": [
            f"Most advice on {topic} is noise. Here's the signal.",
            f"We changed one thing about {topic}. The results surprised us.",
        ],
        "rationale": "Leads with a pattern-interrupt hook, keeps paragraphs short for "
        "scannability, and closes with a single clear CTA aligned to the funnel stage.",
        "posting_guidance": "Post mid-morning on a weekday; ask a question in the first "
        "comment to seed engagement.",
        "repurposing_suggestions": ["Email newsletter", "3 short social posts", "Landing page hero"],
        "recommended_edits": [
            {"area": "Hook", "suggestion": "Test a contrarian opener against a data opener."},
            {"area": "CTA", "suggestion": "Make the benefit of clicking explicit."},
        ],
    }


def _mock_scorecard() -> dict[str, Any]:
    from ..engines.scoring import SCORE_CATEGORIES

    cats = {}
    for key, meta in SCORE_CATEGORIES.items():
        cats[key] = {
            "score": 78,
            "working": f"{meta['label']} is solid and on-spec.",
            "weak": "Minor tightening possible.",
            "improvements": [f"Sharpen {meta['label'].lower()} with a concrete example."],
        }
    return {"overall": 78, "categories": cats,
            "summary": "Strong, publishable draft. Tighten the hook and CTA to push past 85."}


def _mock_research(prompt: str) -> dict[str, Any]:
    topic = _ctx(prompt, "topic") or _ctx(prompt, "objective") or "the category"
    return {
        "trends": [f"Short, opinionated takes on {topic} outperform long explainers",
                   "Native, no-link first posts get more reach"],
        "high_performing_patterns": ["Hook + 3 bullets + 1 CTA", "Personal story -> lesson -> ask"],
        "competitor_observations": ["Competitors over-rely on feature lists; thin on outcomes"],
        "audience_pain_points": ["Too many tools, not enough time", "Hard to prove ROI"],
        "content_gaps": ["Few honest 'what didn't work' posts", "Little plain-English education"],
        "common_hooks": ["Most people get X wrong", "We tried X so you don't have to"],
        "keywords": [topic, f"best {topic}", f"{topic} examples", f"{topic} strategy"],
        "related_questions": [f"How do I start with {topic}?", f"Is {topic} worth it?"],
        "search_intent": "Mostly informational with commercial-investigation overlap.",
        "recommended_angle": f"Lead with a contrarian, outcome-first take on {topic}.",
        "recommended_hook": f"Most advice about {topic} is backwards. Here's what actually works.",
        "recommended_cta": "Invite a reply or comment to drive engagement.",
        "risks": "Avoid unsupported superlatives; cite any statistics.",
        "market_context": "Buyers are cautious; proof and specificity win.",
        "sources": [
            {"title": "Platform best-practices overview", "url": "https://example.com/best-practices",
             "snippet": "Synthesized best-practice patterns.", "source_type": "synthesized"},
        ],
    }


def _mock_repurpose(prompt: str) -> dict[str, Any]:
    return {
        "outputs": [
            {"format": "LinkedIn post", "content": "Hook + 3 bullets + CTA version."},
            {"format": "Email newsletter", "content": "Subject + scannable body + 1 CTA."},
            {"format": "5 short social posts", "content": "1) ... 2) ... 3) ... 4) ... 5) ..."},
            {"format": "X/Twitter thread", "content": "1/ ... 2/ ... 3/ ..."},
        ]
    }


# --------------------------------------------------------------------------- #
# Factories
# --------------------------------------------------------------------------- #
def get_ai_provider() -> AIProvider:
    if settings.ai_enabled:
        try:
            return AnthropicProvider()
        except Exception:  # pragma: no cover - falls back gracefully
            return MockProvider()
    return MockProvider()


def get_research_provider() -> AIProvider:
    # Research reuses the chat provider; the research engine handles web tooling.
    return get_ai_provider()
