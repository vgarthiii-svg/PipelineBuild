"""
Claude Vision integration for the Sports Card Tracker.

Given the front and back images of a sports card, ask Claude to read the card
and return structured identity fields (player, year, brand, set, card number,
parallel/insert, team, sport, rookie flag, condition).

Gracefully degrades: if no ANTHROPIC_API_KEY is set (or the anthropic package
is missing), extraction returns empty fields so the app still works as a manual
tracker.
"""

import base64
import json
import os
from typing import Optional

# Default to the most capable model; override with CARD_VISION_MODEL
# (e.g. "claude-sonnet-4-6" for lower cost on high volume).
DEFAULT_MODEL = os.environ.get("CARD_VISION_MODEL", "claude-opus-4-8")

_EMPTY = {
    "player": "",
    "year": "",
    "brand": "",
    "set_name": "",
    "card_number": "",
    "variation": "",
    "team": "",
    "sport": "",
    "is_rookie": "",
    "condition": "",
    "notes": "",
}

_PROMPT = """You are cataloguing a sports trading card. You are given the FRONT and BACK images of a single card.

Read the card carefully and extract these fields. Use the back of the card for the card number, set, year, and stats if the front is unclear.

Return ONLY a JSON object (no prose, no code fences) with exactly these keys:
- player: the athlete's full name
- year: the card's year or season (e.g. "2023" or "2023-24")
- brand: the manufacturer (e.g. "Topps", "Panini", "Upper Deck", "Bowman", "Fleer")
- set_name: the product/set name (e.g. "Chrome", "Prizm", "Donruss", "Series 1")
- card_number: the card number, including any prefix (e.g. "RC-12", "150")
- variation: any parallel, insert, refractor, or numbering (e.g. "Silver Prizm", "/99", "Refractor"); empty string if base
- team: the team shown on the card
- sport: the sport (e.g. "Baseball", "Basketball", "Football", "Hockey", "Soccer")
- is_rookie: "yes" if it is a rookie card (RC logo or rookie designation), otherwise "no"
- condition: a brief visual condition note based ONLY on what you can see (e.g. "sharp corners, clean surface" or "soft corners, off-center"); empty string if unsure
- notes: anything else notable (autograph, memorabilia/patch, serial number); empty string if none

If a field is not legible or not present, use an empty string. Do not invent values."""


def _get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        print("[VISION] anthropic package not installed")
        return None
    return anthropic.Anthropic(api_key=api_key)


def _image_block(path: str) -> Optional[dict]:
    if not path or not os.path.isfile(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def _parse_json(text: str) -> dict:
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


def extract_card(front_path: str, back_path: Optional[str] = None) -> dict:
    """
    Returns a dict with keys: fields (dict), vision_used (bool), message (str).
    """
    client = _get_client()
    if client is None:
        return {
            "fields": dict(_EMPTY),
            "vision_used": False,
            "message": "No ANTHROPIC_API_KEY set — fill in the fields manually.",
        }

    content = []
    front_block = _image_block(front_path)
    if front_block:
        content.append({"type": "text", "text": "FRONT of the card:"})
        content.append(front_block)
    back_block = _image_block(back_path) if back_path else None
    if back_block:
        content.append({"type": "text", "text": "BACK of the card:"})
        content.append(back_block)
    content.append({"type": "text", "text": _PROMPT})

    if not front_block and not back_block:
        return {
            "fields": dict(_EMPTY),
            "vision_used": False,
            "message": "No images supplied.",
        }

    try:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
        raw = _parse_json(text)
    except Exception as exc:  # noqa: BLE001 - surface any failure as a manual fallback
        return {
            "fields": dict(_EMPTY),
            "vision_used": False,
            "message": f"Vision extraction failed: {exc}",
        }

    fields = dict(_EMPTY)
    for key in fields:
        value = raw.get(key, "")
        fields[key] = "" if value is None else str(value).strip()

    return {"fields": fields, "vision_used": True, "message": "Card read by Claude Vision."}
