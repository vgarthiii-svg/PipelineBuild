"""
Best-effort ESPN fantasy-football draft sync.

ESPN has no official public API; this uses the read endpoints the web app
calls. For a PRIVATE league you must supply the `espn_s2` and `SWID` cookies
from a logged-in browser session. This runs on the user's machine (not this
sandbox), so network access and credentials live there.

Draft slot is derived from the overall pick number using the same snake math
as the engine, so we never need to map ESPN's internal team ids.
"""
import re

BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"


def normalize_name(name: str) -> str:
    """Loose key for matching names across sources (case/punct/suffix-insensitive)."""
    n = (name or "").lower()
    n = re.sub(r"[.'`]", "", n)
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _cookies(espn_s2, swid):
    if not (espn_s2 and swid):
        return None
    swid = swid if swid.startswith("{") else "{" + swid.strip("{}") + "}"
    return {"espn_s2": espn_s2, "SWID": swid}


def fetch_draft_picks(league_id, season, espn_s2=None, swid=None, timeout=15):
    """
    Return list of {overall_pick, espn_player_id, player_name} for a league's
    draft, newest math derived by caller. Raises RuntimeError with a friendly
    message on any failure (auth, network, not-drafted-yet).
    """
    import httpx  # local import so the app boots even if httpx isn't present

    base = BASE.format(season=season)
    cookies = _cookies(espn_s2, swid)
    headers = {"User-Agent": "Mozilla/5.0 (draft-tracker)"}

    try:
        with httpx.Client(timeout=timeout, headers=headers, cookies=cookies, follow_redirects=True) as c:
            draft_url = f"{base}/segments/0/leagues/{league_id}"
            r = c.get(draft_url, params={"view": "mDraftDetail"})
            if r.status_code in (401, 403):
                raise RuntimeError(
                    "ESPN denied access. For a private league, provide valid espn_s2 and SWID cookies."
                )
            if r.status_code == 404:
                raise RuntimeError("League not found for that id/season on ESPN.")
            r.raise_for_status()
            data = r.json()

            detail = (data or {}).get("draftDetail") or {}
            raw_picks = detail.get("picks") or []
            if not raw_picks:
                raise RuntimeError("No draft picks yet on ESPN (draft may not have started).")

            player_ids = sorted({p.get("playerId") for p in raw_picks if p.get("playerId")})
            names = _fetch_player_names(c, base, league_id, player_ids)

            out = []
            for p in raw_picks:
                overall = p.get("overallPickNumber")
                pid = p.get("playerId")
                if not overall or not pid:
                    continue
                out.append({
                    "overall_pick": overall,
                    "espn_player_id": pid,
                    "player_name": names.get(pid, f"ESPN player {pid}"),
                })
            out.sort(key=lambda x: x["overall_pick"])
            return out
    except RuntimeError:
        raise
    except Exception as e:  # network, JSON, etc.
        raise RuntimeError(f"Could not reach ESPN: {e}")


def _fetch_player_names(client, base, league_id, player_ids):
    """Map ESPN playerId -> full name via the league's player-info view."""
    if not player_ids:
        return {}
    import json as _json

    url = f"{base}/segments/0/leagues/{league_id}"
    filt = {"players": {"filterIds": {"value": list(player_ids)}}}
    try:
        r = client.get(
            url,
            params={"view": "kona_player_info"},
            headers={"X-Fantasy-Filter": _json.dumps(filt)},
        )
        r.raise_for_status()
        data = r.json()
        out = {}
        for entry in (data or {}).get("players", []):
            pid = entry.get("id")
            info = entry.get("player") or {}
            full = info.get("fullName")
            if pid and full:
                out[pid] = full
        return out
    except Exception:
        # Names are a nicety; the pick still records by id if this fails.
        return {}
