"""
PPR Draft Board: browse, filter, and open player profiles from imported
fantasy-football rankings.
"""
from typing import List, Optional

import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PlayerRanking
from sqlalchemy import func

from app.schemas import PlayerRankingOut, RankingsMeta, RankingsImportResult, RankingSource
from app.services import rankings_import

router = APIRouter(prefix="/api/rankings", tags=["rankings"])

DEFAULT_SOURCE = rankings_import.DEFAULT_SOURCE


def _position_rank_map(db: Session, source: str) -> dict:
    """player_ranking.id -> rank within its position (ordered by overall rank)."""
    rows = (
        db.query(PlayerRanking)
        .filter(PlayerRanking.source == source)
        .order_by(PlayerRanking.rank.asc())
        .all()
    )
    counters: dict = {}
    out: dict = {}
    for r in rows:
        pos = r.position or "?"
        counters[pos] = counters.get(pos, 0) + 1
        out[r.id] = counters[pos]
    return out


def _to_out(r: PlayerRanking, pos_rank: Optional[int]) -> PlayerRankingOut:
    value_delta = None
    if r.expert_rank is not None and r.rank is not None:
        value_delta = round(r.expert_rank - r.rank, 2)
    return PlayerRankingOut(
        id=r.id,
        source=r.source,
        player_id=r.player_id,
        rank=r.rank,
        name=r.name,
        team=r.team,
        position=r.position,
        position_rank=pos_rank,
        tier=r.tier,
        mason_dodd_rank=r.mason_dodd_rank,
        expert_rank=r.expert_rank,
        value_delta=value_delta,
    )


@router.get("", response_model=List[PlayerRankingOut])
@router.get("/", response_model=List[PlayerRankingOut])
def list_rankings(
    source: str = DEFAULT_SOURCE,
    position: Optional[str] = None,
    tier: Optional[str] = None,
    team: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(400, le=1000),
    db: Session = Depends(get_db),
):
    """Ranked player list for a source, with optional position/tier/team/name filters."""
    query = db.query(PlayerRanking).filter(PlayerRanking.source == source)
    if position:
        query = query.filter(PlayerRanking.position == position.upper())
    if tier:
        query = query.filter(PlayerRanking.tier == tier.upper())
    if team:
        query = query.filter(PlayerRanking.team == team.upper())
    if q:
        query = query.filter(PlayerRanking.name.ilike(f"%{q}%"))

    rows = query.order_by(PlayerRanking.rank.asc()).limit(limit).all()
    pos_ranks = _position_rank_map(db, source)
    return [_to_out(r, pos_ranks.get(r.id)) for r in rows]


@router.get("/sources", response_model=List[RankingSource])
def list_sources(db: Session = Depends(get_db)):
    """Available ranking sources (one per imported file) with player counts."""
    rows = (
        db.query(PlayerRanking.source, func.count(PlayerRanking.id))
        .group_by(PlayerRanking.source)
        .order_by(PlayerRanking.source.asc())
        .all()
    )
    return [RankingSource(source=s, count=c) for s, c in rows]


@router.get("/meta", response_model=RankingsMeta)
def rankings_meta(source: str = DEFAULT_SOURCE, db: Session = Depends(get_db)):
    """Distinct positions/tiers/teams plus counts, for building filter controls."""
    rows = db.query(PlayerRanking).filter(PlayerRanking.source == source).all()
    positions, tiers, teams = set(), set(), set()
    pos_counts, tier_counts = {}, {}
    for r in rows:
        if r.position:
            positions.add(r.position)
            pos_counts[r.position] = pos_counts.get(r.position, 0) + 1
        if r.tier:
            tiers.add(r.tier)
            tier_counts[r.tier] = tier_counts.get(r.tier, 0) + 1
        if r.team:
            teams.add(r.team)

    # Positions in a fantasy-natural order, unknowns appended.
    pos_order = ["QB", "RB", "WR", "TE", "K", "DST"]
    ordered_positions = [p for p in pos_order if p in positions] + sorted(
        p for p in positions if p not in pos_order
    )
    return RankingsMeta(
        source=source,
        total=len(rows),
        positions=ordered_positions,
        tiers=sorted(tiers),
        teams=sorted(teams),
        position_counts=pos_counts,
        tier_counts=tier_counts,
    )


@router.post("/import", response_model=RankingsImportResult)
def import_rankings(source: str = DEFAULT_SOURCE, db: Session = Depends(get_db)):
    """(Re)load the bundled rankings CSV, upserting by player_id."""
    result = rankings_import.import_rankings(db, rankings_import.DEFAULT_CSV, source)
    return RankingsImportResult(source=source, **result)


@router.post("/upload", response_model=RankingsImportResult)
async def upload_rankings(
    file: UploadFile = File(...),
    source: str = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload a rankings CSV and import it as a named source. If `source` is
    omitted, the file name (without extension) becomes the source name.
    Expected columns: player_id, Rank, Name, Team, Position, Tier,
    Mason Dodd Rank, Expert Rank (only Name is required).
    """
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded CSV text.")

    source_name = (source or "").strip()
    if not source_name:
        base = os.path.basename(file.filename or "").rsplit(".", 1)[0]
        source_name = base.strip() or "Uploaded rankings"

    result = rankings_import.import_text(db, text, source_name)
    if result["total"] == 0:
        raise HTTPException(
            status_code=400,
            detail="No player rows found. The CSV needs a header row with a 'Name' column.",
        )
    return RankingsImportResult(source=source_name, **result)


@router.get("/{player_id}", response_model=PlayerRankingOut)
def get_player(player_id: int, source: str = DEFAULT_SOURCE, db: Session = Depends(get_db)):
    """Full profile + ranking data for one player (by external player_id)."""
    r = (
        db.query(PlayerRanking)
        .filter(PlayerRanking.source == source, PlayerRanking.player_id == player_id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Player not found in this source")
    pos_ranks = _position_rank_map(db, source)
    return _to_out(r, pos_ranks.get(r.id))
