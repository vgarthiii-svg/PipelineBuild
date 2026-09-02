"""
Import fantasy-football player rankings from a CSV into the player_rankings
table. Upserts by (source, player_id) so re-running refreshes in place.

Expected columns (header row):
    player_id, Rank, Name, Team, Position, Tier, Mason Dodd Rank, Expert Rank
"""
import csv
import os

from sqlalchemy.orm import Session

from app.models import PlayerRanking

DEFAULT_SOURCE = "REDRAFT PPR"
DEFAULT_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "ppr_redraft_rankings.csv",
)


def _to_int(val):
    if val is None:
        return None
    val = str(val).strip()
    if val in ("", "-", "N/A", "NA"):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _to_float(val):
    if val is None:
        return None
    val = str(val).strip()
    if val in ("", "-", "N/A", "NA"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_rows(path=DEFAULT_CSV):
    """Yield normalized dicts from the rankings CSV."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Name") or "").strip()
            if not name:
                continue
            yield {
                "player_id": _to_int(row.get("player_id")),
                "rank": _to_int(row.get("Rank")),
                "name": name,
                "team": (row.get("Team") or "").strip() or None,
                "position": (row.get("Position") or "").strip() or None,
                "tier": (row.get("Tier") or "").strip() or None,
                "mason_dodd_rank": _to_int(row.get("Mason Dodd Rank")),
                "expert_rank": _to_float(row.get("Expert Rank")),
            }


def import_rankings(db: Session, path=DEFAULT_CSV, source=DEFAULT_SOURCE):
    """
    Upsert rows from `path` into player_rankings under `source`.
    Returns {"imported": n_new, "updated": n_existing, "total": n_in_source}.
    """
    imported = 0
    updated = 0
    for data in parse_rows(path):
        existing = None
        if data["player_id"] is not None:
            existing = (
                db.query(PlayerRanking)
                .filter(
                    PlayerRanking.source == source,
                    PlayerRanking.player_id == data["player_id"],
                )
                .first()
            )
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(PlayerRanking(source=source, **data))
            imported += 1
    db.commit()
    total = db.query(PlayerRanking).filter(PlayerRanking.source == source).count()
    return {"imported": imported, "updated": updated, "total": total}


def seed_rankings(db: Session):
    """Load the bundled rankings CSV on first run if the table is empty."""
    if db.query(PlayerRanking).count() > 0:
        return
    if not os.path.exists(DEFAULT_CSV):
        return
    import_rankings(db, DEFAULT_CSV, DEFAULT_SOURCE)
