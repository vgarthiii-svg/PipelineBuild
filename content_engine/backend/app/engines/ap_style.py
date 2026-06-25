"""AP-style / journalistic compliance checker.

This is a practical, rule-based checker built on generally known journalistic
writing principles. It does NOT reproduce any copyrighted stylebook text.
Users can add custom editorial rules (stored as StyleGuideRule rows) which are
merged in at check time.

Each finding: {rule, category, severity, message, matches, count}.
"""
from __future__ import annotations

import re
from typing import Any

# Hype / fluff words that journalistic writing avoids without support.
HYPE_WORDS = [
    "revolutionary", "game-changer", "game changer", "cutting-edge", "world-class",
    "best-in-class", "synergy", "leverage", "disrupt", "paradigm", "next-level",
    "unprecedented", "seamless", "robust", "turnkey", "bleeding-edge", "ninja",
    "rockstar", "guru", "unparalleled", "groundbreaking", "must-have",
]

WEASEL_PHRASES = [
    "very", "really", "just", "simply", "actually", "basically", "literally",
    "in order to", "a lot of", "kind of", "sort of", "needless to say",
]

PASSIVE_RE = re.compile(r"\b(?:is|are|was|were|be|been|being)\s+\w+ed\b", re.IGNORECASE)
EXCLAIM_RE = re.compile(r"!")
ALLCAPS_RE = re.compile(r"\b[A-Z]{4,}\b")
# Numbers one..nine written should be words; figures 10+ as digits.
SPELL_OUT_RE = re.compile(r"\b([1-9])\b(?!\s*(?:%|st|nd|rd|th|:|\.\d|[ap]\.?m))")
LONG_SENTENCE_WORDS = 30


def _matches(pattern: list[str], text: str) -> list[str]:
    found = []
    low = text.lower()
    for w in pattern:
        if re.search(rf"\b{re.escape(w.lower())}\b", low):
            found.append(w)
    return found


def check(text: str, custom_rules: list[dict] | None = None) -> dict[str, Any]:
    """Run all checks. Returns findings + a 0-100 ap_score."""
    findings: list[dict] = []
    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

    def add(rule, category, severity, message, matches=None):
        findings.append({
            "rule": rule, "category": category, "severity": severity,
            "message": message, "matches": matches or [], "count": len(matches or []),
        })

    # Hype / unsupported superlatives
    hype = _matches(HYPE_WORDS, text)
    if hype:
        add("Avoid hype and fluff", "hype", "warning",
            "Replace hype words with specific, provable statements.", hype)

    # Weasel / filler words
    weasel = _matches(WEASEL_PHRASES, text)
    if weasel:
        add("Cut filler and weasel words", "concision", "info",
            "Tighten by removing filler words.", weasel)

    # Passive voice
    passive = PASSIVE_RE.findall(text)
    if len(passive) >= 2:
        add("Prefer active voice", "active_voice", "warning",
            f"{len(passive)} likely passive constructions — prefer active voice.", passive[:8])

    # Exclamation overuse
    bangs = EXCLAIM_RE.findall(text)
    if len(bangs) > 1:
        add("Limit exclamation points", "tone", "info",
            "Journalistic style uses exclamation points sparingly.", bangs)

    # ALL CAPS
    caps = ALLCAPS_RE.findall(text)
    caps = [c for c in caps if c not in ("CTA", "SEO", "FAQ", "CEO", "API", "AP")]
    if caps:
        add("Avoid ALL-CAPS for emphasis", "capitalization", "info",
            "Use sentence case; avoid shouting in caps.", caps[:8])

    # Numeral consistency (one through nine spelled out)
    bare_small = SPELL_OUT_RE.findall(text)
    if bare_small:
        add("Spell out numbers one through nine", "numerals", "info",
            "Spell out 1-9; use figures for 10 and above.", bare_small[:8])

    # Long sentences (readability)
    long_sents = [s for s in sentences if len(s.split()) > LONG_SENTENCE_WORDS]
    if long_sents:
        add("Shorten long sentences", "readability", "warning",
            f"{len(long_sents)} sentence(s) exceed {LONG_SENTENCE_WORDS} words — split for clarity.",
            [s[:60] + "…" for s in long_sents[:4]])

    # Unsupported claims heuristic: superlative + no number nearby
    if re.search(r"\b(?:best|fastest|cheapest|only|leading|#1|number one)\b", text, re.IGNORECASE) \
            and not re.search(r"\d", text):
        add("Support strong claims", "credibility", "warning",
            "Strong/superlative claim made without any supporting figure or source.", [])

    # Custom user rules
    for cr in (custom_rules or []):
        det = cr.get("detection") or {}
        typ = det.get("type")
        try:
            if typ == "regex" and det.get("pattern"):
                m = re.findall(det["pattern"], text, re.IGNORECASE)
                if m:
                    add(cr.get("name", "Custom rule"), cr.get("category", "custom"),
                        cr.get("severity", "warning"), det.get("message", cr.get("rule", "")),
                        [str(x) for x in m[:8]])
            elif typ == "phrase" and det.get("pattern"):
                m = _matches([p.strip() for p in det["pattern"].split(",")], text)
                if m:
                    add(cr.get("name", "Custom rule"), cr.get("category", "custom"),
                        cr.get("severity", "warning"), det.get("message", cr.get("rule", "")), m)
        except re.error:
            continue

    # Scoring: start at 100, subtract weighted penalties.
    penalty = 0
    weights = {"error": 12, "warning": 6, "info": 2}
    for f in findings:
        penalty += weights.get(f["severity"], 4) * min(f["count"] or 1, 3)
    ap_score = max(0, min(100, 100 - penalty))

    return {
        "ap_score": ap_score,
        "word_count": word_count,
        "sentence_count": len(sentences),
        "findings": findings,
        "passes": ap_score >= 80,
    }
