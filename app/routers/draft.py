"""
Live Draft tracker: run a snake draft against a ranking source, marking
players off the board manually (click-to-draft) or via best-effort ESPN sync.
"""
import json
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DraftSession, DraftPick, PlayerRanking
from app.schemas import DraftStartIn, DraftPickIn, EspnSyncIn
from app.services import draft_engine, espn_draft
from app.services import rankings_import

router = APIRouter(prefix="/api/draft", tags=["draft"])


def _active(db: Session) -> Optional[DraftSession]:
    return (
        db.query(DraftSession)
        .filter(DraftSession.status == "active")
        .order_by(DraftSession.id.desc())
        .first()
    )


def _default_teams(num_teams, my_slot, jake_slot):
    teams = []
    for slot in range(1, num_teams + 1):
        tag = "me" if slot == my_slot else ("jake" if slot == jake_slot else None)
        name = "You" if tag == "me" else ("Jake" if tag == "jake" else f"Team {slot}")
        teams.append({"slot": slot, "name": name, "owner_tag": tag})
    return teams


def _source_by_name_map(db: Session, source: str):
    """normalized player name -> PlayerRanking, for the given source."""
    rows = db.query(PlayerRanking).filter(PlayerRanking.source == source).all()
    return {espn_draft.normalize_name(r.name): r for r in rows}


@router.post("/start")
def start_draft(body: DraftStartIn, db: Session = Depends(get_db)):
    """Begin a new draft. Any previously active draft is closed."""
    source = body.source or rankings_import.DEFAULT_SOURCE
    # Validate the source has players.
    if db.query(PlayerRanking).filter(PlayerRanking.source == source).count() == 0:
        raise HTTPException(status_code=400, detail=f"Ranking source '{source}' has no players.")

    # Close any existing active drafts.
    for s in db.query(DraftSession).filter(DraftSession.status == "active").all():
        s.status = "complete"

    if body.teams:
        teams = [t.dict() for t in body.teams]
    else:
        teams = _default_teams(body.num_teams, body.my_slot, body.jake_slot)

    session = DraftSession(
        name=body.name,
        source=source,
        num_teams=body.num_teams,
        rounds=body.rounds,
        snake=body.snake,
        current_pick=1,
        teams_json=json.dumps(teams),
        espn_league_id=body.espn_league_id,
        espn_season=body.espn_season or (date.today().year),
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return draft_engine.build_state(db, session)


@router.get("/current")
def current_draft(db: Session = Depends(get_db)):
    """The active draft's full state, or {active: false} if none."""
    session = _active(db)
    if not session:
        return {"active": False}
    state = draft_engine.build_state(db, session)
    state["active"] = True
    return state


@router.get("/best-available")
def best_available(position: Optional[str] = None, limit: int = Query(50, le=500), db: Session = Depends(get_db)):
    session = _active(db)
    if not session:
        raise HTTPException(status_code=404, detail="No active draft.")
    rows = draft_engine.best_available(db, session, position=position, limit=limit)
    picks = db.query(DraftPick).filter(DraftPick.session_id == session.id).count()
    return {
        "source": session.source,
        "drafted_count": picks,
        "players": [
            {
                "player_id": r.player_id, "rank": r.rank, "name": r.name, "team": r.team,
                "position": r.position, "tier": r.tier,
                "mason_dodd_rank": r.mason_dodd_rank, "expert_rank": r.expert_rank,
            }
            for r in rows
        ],
    }


@router.post("/pick")
def make_pick(body: DraftPickIn, db: Session = Depends(get_db)):
    """Record the on-the-clock selection and advance the draft."""
    session = _active(db)
    if not session:
        raise HTTPException(status_code=404, detail="No active draft.")
    total = session.num_teams * session.rounds
    if session.current_pick > total:
        raise HTTPException(status_code=400, detail="Draft is complete.")

    overall = session.current_pick
    rnd, pir, slot = draft_engine.pick_coords(overall, session.num_teams, session.snake)
    if body.team_slot:
        slot = body.team_slot

    # Resolve the player from the ranking source (by id, else by name).
    row = None
    if body.player_id is not None:
        row = (
            db.query(PlayerRanking)
            .filter(PlayerRanking.source == session.source, PlayerRanking.player_id == body.player_id)
            .first()
        )
    if row is None and body.player_name:
        nmap = _source_by_name_map(db, session.source)
        row = nmap.get(espn_draft.normalize_name(body.player_name))

    if row is None and not body.player_name:
        raise HTTPException(status_code=400, detail="Provide player_id or player_name.")

    name = row.name if row else body.player_name
    # Guard against drafting the same player twice.
    existing_names = {
        (p.player_name or "").strip().lower()
        for p in db.query(DraftPick).filter(DraftPick.session_id == session.id).all()
    }
    if name.strip().lower() in existing_names:
        raise HTTPException(status_code=409, detail=f"{name} is already drafted.")

    pick = DraftPick(
        session_id=session.id,
        overall_pick=overall,
        round=rnd,
        pick_in_round=pir,
        team_slot=slot,
        player_id=row.player_id if row else None,
        player_name=name,
        position=row.position if row else None,
        nfl_team=row.team if row else None,
        source_rank=row.rank if row else None,
        via="manual",
    )
    db.add(pick)
    session.current_pick = overall + 1
    if session.current_pick > total:
        session.status = "complete"
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return draft_engine.build_state(db, session)


@router.post("/undo")
def undo_pick(db: Session = Depends(get_db)):
    """Remove the most recent pick and hand the clock back."""
    session = _active(db)
    if not session:
        # Maybe the last pick completed the draft; reactivate the latest.
        session = db.query(DraftSession).order_by(DraftSession.id.desc()).first()
    if not session:
        raise HTTPException(status_code=404, detail="No draft to undo.")

    last = (
        db.query(DraftPick)
        .filter(DraftPick.session_id == session.id)
        .order_by(DraftPick.overall_pick.desc())
        .first()
    )
    if not last:
        raise HTTPException(status_code=400, detail="No picks to undo.")
    session.current_pick = last.overall_pick
    session.status = "active"
    db.delete(last)
    db.commit()
    db.refresh(session)
    state = draft_engine.build_state(db, session)
    state["active"] = True
    return state


@router.post("/reset")
def reset_draft(db: Session = Depends(get_db)):
    """Delete the active draft (and its picks)."""
    session = _active(db)
    if session:
        db.delete(session)
        db.commit()
    return {"active": False}


@router.post("/espn-sync")
def espn_sync(body: EspnSyncIn, db: Session = Depends(get_db)):
    """
    Pull picks from ESPN and reconcile them into the active draft. Best-effort:
    on any ESPN error the draft is untouched and the error is returned.
    """
    session = _active(db)
    if not session:
        raise HTTPException(status_code=404, detail="No active draft.")

    league_id = body.league_id or session.espn_league_id
    season = body.season or session.espn_season
    if not league_id:
        raise HTTPException(status_code=400, detail="No ESPN league id set for this draft.")

    try:
        espn_picks = espn_draft.fetch_draft_picks(
            league_id, season, espn_s2=body.espn_s2, swid=body.swid
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Persist league id for future syncs.
    session.espn_league_id = str(league_id)
    session.espn_season = season

    recorded = {
        p.overall_pick
        for p in db.query(DraftPick).filter(DraftPick.session_id == session.id).all()
    }
    nmap = _source_by_name_map(db, session.source)

    added = 0
    for ep in espn_picks:
        overall = ep["overall_pick"]
        if overall in recorded:
            continue
        rnd, pir, slot = draft_engine.pick_coords(overall, session.num_teams, session.snake)
        row = nmap.get(espn_draft.normalize_name(ep["player_name"]))
        db.add(DraftPick(
            session_id=session.id,
            overall_pick=overall,
            round=rnd,
            pick_in_round=pir,
            team_slot=slot,
            player_id=row.player_id if row else None,
            player_name=row.name if row else ep["player_name"],
            position=row.position if row else None,
            nfl_team=row.team if row else None,
            source_rank=row.rank if row else None,
            via="espn",
        ))
        recorded.add(overall)
        added += 1

    if recorded:
        session.current_pick = max(recorded) + 1
    total = session.num_teams * session.rounds
    session.status = "complete" if session.current_pick > total else "active"
    db.commit()
    db.refresh(session)
    state = draft_engine.build_state(db, session)
    state["synced"] = added
    state["active"] = True
    return state
