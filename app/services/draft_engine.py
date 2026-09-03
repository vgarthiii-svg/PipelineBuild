"""
Snake-draft math and live-state assembly for the Live Draft tracker.
Pure functions where possible so the pick ordering is easy to test.
"""
import json

from sqlalchemy.orm import Session

from app.models import DraftSession, DraftPick, PlayerRanking


def pick_coords(overall: int, num_teams: int, snake: bool):
    """Map a 1-based overall pick to (round, pick_in_round, team_slot)."""
    rnd = (overall - 1) // num_teams + 1
    pir = (overall - 1) % num_teams + 1
    if snake and rnd % 2 == 0:
        slot = num_teams - pir + 1
    else:
        slot = pir
    return rnd, pir, slot


def team_upcoming_picks(slot, from_pick, num_teams, rounds, snake, limit=5):
    """Overall pick numbers on or after `from_pick` that belong to `slot`."""
    total = num_teams * rounds
    out = []
    for overall in range(from_pick, total + 1):
        _, _, s = pick_coords(overall, num_teams, snake)
        if s == slot:
            out.append(overall)
            if len(out) >= limit:
                break
    return out


def _teams(session: DraftSession):
    try:
        return json.loads(session.teams_json) if session.teams_json else []
    except (ValueError, TypeError):
        return []


def _team_by_slot(teams, slot):
    for t in teams:
        if t.get("slot") == slot:
            return t
    return {"slot": slot, "name": f"Team {slot}", "owner_tag": None}


def owner_next(session: DraftSession, teams, owner_tag):
    """Next upcoming pick + how many picks away, for the team tagged owner_tag."""
    slot = next((t["slot"] for t in teams if t.get("owner_tag") == owner_tag), None)
    if slot is None:
        return None
    upcoming = team_upcoming_picks(
        slot, session.current_pick, session.num_teams, session.rounds, session.snake, limit=3
    )
    if not upcoming:
        return {"slot": slot, "on_the_clock": False, "next_overall": None, "picks_until": None, "upcoming": []}
    nxt = upcoming[0]
    return {
        "slot": slot,
        "on_the_clock": nxt == session.current_pick,
        "next_overall": nxt,
        "picks_until": nxt - session.current_pick,
        "upcoming": upcoming,
    }


def build_state(db: Session, session: DraftSession):
    """Assemble the full live-draft state the UI renders from."""
    teams = _teams(session)
    total_picks = session.num_teams * session.rounds
    picks = (
        db.query(DraftPick)
        .filter(DraftPick.session_id == session.id)
        .order_by(DraftPick.overall_pick.asc())
        .all()
    )
    drafted_ids = {p.player_id for p in picks if p.player_id is not None}
    drafted_names = {(p.player_name or "").strip().lower() for p in picks}

    complete = session.current_pick > total_picks
    if complete:
        on_clock = None
    else:
        rnd, pir, slot = pick_coords(session.current_pick, session.num_teams, session.snake)
        t = _team_by_slot(teams, slot)
        on_clock = {
            "overall": session.current_pick,
            "round": rnd,
            "pick_in_round": pir,
            "team_slot": slot,
            "team_name": t.get("name"),
            "owner_tag": t.get("owner_tag"),
        }

    # Rosters per slot, in pick order.
    rosters = {t["slot"]: [] for t in teams}
    for p in picks:
        rosters.setdefault(p.team_slot, []).append({
            "overall_pick": p.overall_pick,
            "round": p.round,
            "player_name": p.player_name,
            "position": p.position,
            "nfl_team": p.nfl_team,
        })

    return {
        "session_id": session.id,
        "name": session.name,
        "source": session.source,
        "num_teams": session.num_teams,
        "rounds": session.rounds,
        "snake": session.snake,
        "total_picks": total_picks,
        "current_pick": session.current_pick,
        "complete": complete,
        "on_the_clock": on_clock,
        "teams": teams,
        "me": owner_next(session, teams, "me"),
        "jake": owner_next(session, teams, "jake"),
        "picks": [
            {
                "overall_pick": p.overall_pick,
                "round": p.round,
                "pick_in_round": p.pick_in_round,
                "team_slot": p.team_slot,
                "player_id": p.player_id,
                "player_name": p.player_name,
                "position": p.position,
                "nfl_team": p.nfl_team,
                "source_rank": p.source_rank,
                "via": p.via,
            }
            for p in picks
        ],
        "rosters": rosters,
        "drafted_count": len(picks),
        "espn_league_id": session.espn_league_id,
    }


def best_available(db: Session, session: DraftSession, position=None, limit=50):
    """Undrafted players from the session's ranking source, best first."""
    picks = db.query(DraftPick).filter(DraftPick.session_id == session.id).all()
    drafted_ids = {p.player_id for p in picks if p.player_id is not None}
    drafted_names = {(p.player_name or "").strip().lower() for p in picks}

    q = db.query(PlayerRanking).filter(PlayerRanking.source == session.source)
    if position:
        q = q.filter(PlayerRanking.position == position.upper())
    rows = q.order_by(PlayerRanking.rank.asc()).all()

    out = []
    for r in rows:
        if r.player_id in drafted_ids:
            continue
        if (r.name or "").strip().lower() in drafted_names:
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out
