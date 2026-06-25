"""Seed system data: platform rules + default AP-style/system style rules.

Idempotent — only inserts rows that don't already exist. Runs on startup.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .engines.platform_rules import PLATFORM_RULE_SEED
from .models import PlatformRule, StyleGuideRule

SYSTEM_STYLE_RULES = [
    {"name": "Avoid hype words", "category": "hype", "severity": "warning",
     "rule": "Replace hype/marketing-speak with specific, provable statements.",
     "detection": {"type": "phrase", "pattern": "revolutionary, game-changer, world-class, cutting-edge, seamless, robust"}},
    {"name": "Prefer active voice", "category": "active_voice", "severity": "warning",
     "rule": "Use active voice; name the actor.", "detection": {"type": "heuristic"}},
    {"name": "Spell out small numbers", "category": "numerals", "severity": "info",
     "rule": "Spell out one through nine; use figures for 10+.", "detection": {"type": "heuristic"}},
    {"name": "Support strong claims", "category": "credibility", "severity": "warning",
     "rule": "Back superlatives with a figure or source.", "detection": {"type": "heuristic"}},
]


def seed_platform_rules(db: Session) -> int:
    inserted = 0
    for r in PLATFORM_RULE_SEED:
        exists = db.scalar(
            select(PlatformRule).where(
                PlatformRule.platform == r["platform"],
                PlatformRule.content_type == r["content_type"],
            )
        )
        if exists:
            continue
        db.add(PlatformRule(
            platform=r["platform"], content_type=r["content_type"], label=r["label"],
            structure=r["structure"], best_practices=r["best_practices"],
            constraints=r["constraints"], is_system=True,
        ))
        inserted += 1
    db.commit()
    return inserted


def seed_style_rules(db: Session) -> int:
    inserted = 0
    for r in SYSTEM_STYLE_RULES:
        exists = db.scalar(
            select(StyleGuideRule).where(
                StyleGuideRule.name == r["name"], StyleGuideRule.is_system.is_(True)
            )
        )
        if exists:
            continue
        db.add(StyleGuideRule(
            user_id=None, brand_id=None, name=r["name"], category=r["category"],
            rule=r["rule"], detection=r["detection"], severity=r["severity"],
            is_system=True, enabled=True,
        ))
        inserted += 1
    db.commit()
    return inserted


def seed_all(db: Session) -> dict[str, int]:
    return {
        "platform_rules": seed_platform_rules(db),
        "style_rules": seed_style_rules(db),
    }
