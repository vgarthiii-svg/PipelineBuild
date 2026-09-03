#!/usr/bin/env python3
"""
Pre-draft ESPN connectivity check. Run this on YOUR machine (not the app)
to confirm the app can reach your league and read the draft before draft day.

Usage:
    # public league:
    python scripts/espn_draft_test.py <LEAGUE_ID> [SEASON]

    # private league (cookies from a logged-in ESPN browser session):
    ESPN_S2='AEB...long...' SWID='{XXXXXXXX-XXXX-...}' \
        python scripts/espn_draft_test.py <LEAGUE_ID> [SEASON]

What it reports:
    1. Connectivity + auth  — can we read the league at all?
    2. Draft state          — how many picks exist (0 before the draft is fine;
                              it still proves the connection works).
    3. A few picks          — so you can eyeball that names look right.
"""
import os
import sys
import json

BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leagues/{lid}"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    league_id = sys.argv[1]
    season = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    espn_s2 = os.environ.get("ESPN_S2")
    swid = os.environ.get("SWID")

    try:
        import httpx
    except ImportError:
        print("httpx not installed. Run:  pip install -r requirements.txt")
        sys.exit(1)

    cookies = None
    if espn_s2 and swid:
        swid = swid if swid.startswith("{") else "{" + swid.strip("{}") + "}"
        cookies = {"espn_s2": espn_s2, "SWID": swid}
        print(f"[auth] using cookies (private league)")
    else:
        print("[auth] no cookies given — assuming a PUBLIC league")

    url = BASE.format(season=season, lid=league_id)
    headers = {"User-Agent": "Mozilla/5.0 (draft-test)"}

    with httpx.Client(timeout=20, headers=headers, cookies=cookies, follow_redirects=True) as c:
        # 1) Connectivity + auth
        r = c.get(url, params={"view": "mTeam"})
        if r.status_code in (401, 403):
            print(f"[FAIL] {r.status_code} — access denied. "
                  "Private league needs valid ESPN_S2 and SWID cookies.")
            sys.exit(2)
        if r.status_code == 404:
            print(f"[FAIL] 404 — no league {league_id} for season {season}. Check the id/season.")
            sys.exit(2)
        r.raise_for_status()
        data = r.json()
        teams = data.get("teams", [])
        name = (data.get("settings") or {}).get("name", "(name hidden)")
        print(f"[ok] connected: league '{name}', season {season}, {len(teams)} teams")

        # 2) Draft state
        r2 = c.get(url, params={"view": "mDraftDetail"})
        r2.raise_for_status()
        picks = ((r2.json() or {}).get("draftDetail") or {}).get("picks") or []
        print(f"[ok] draftDetail reachable — {len(picks)} pick(s) so far "
              f"({'draft not started yet — connection still confirmed' if not picks else 'draft in progress/done'})")

        # 3) Sample picks with names
        if picks:
            pids = sorted({p.get("playerId") for p in picks if p.get("playerId")})
            names = fetch_names(c, url, pids)
            print("[sample] first picks:")
            for p in sorted(picks, key=lambda x: x.get("overallPickNumber", 0))[:8]:
                pid = p.get("playerId")
                print(f"    #{p.get('overallPickNumber'):>3}  {names.get(pid, 'player ' + str(pid))}")
    print("\nDone. If you got '[ok] connected', the app's ESPN Sync will work with these same values.")


def fetch_names(client, url, player_ids):
    if not player_ids:
        return {}
    filt = {"players": {"filterIds": {"value": list(player_ids)}}}
    try:
        r = client.get(url, params={"view": "kona_player_info"},
                       headers={"X-Fantasy-Filter": json.dumps(filt)})
        r.raise_for_status()
        out = {}
        for e in (r.json() or {}).get("players", []):
            info = e.get("player") or {}
            if e.get("id") and info.get("fullName"):
                out[e["id"]] = info["fullName"]
        return out
    except Exception:
        return {}


if __name__ == "__main__":
    main()
