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

DEFAULT_SOURCE = "Mason Dodd PPR Redraft 2026"
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


REQUIRED_COLUMNS = {"Name"}


def _normalize(row: dict):
    name = (row.get("Name") or "").strip()
    if not name:
        return None
    return {
        "player_id": _to_int(row.get("player_id")),
        "rank": _to_int(row.get("Rank")),
        "name": name,
        "team": (row.get("Team") or "").strip() or None,
        "position": (row.get("Position") or "").strip() or None,
        "tier": (row.get("Tier") or "").strip() or None,
        "mason_dodd_rank": _to_int(row.get("Mason Dodd Rank")),
        "expert_rank": _to_float(row.get("Expert Rank")),
    }


def parse_reader(reader):
    """Yield normalized dicts from a csv.DictReader."""
    for row in reader:
        data = _normalize(row)
        if data:
            yield data


def parse_rows(path=DEFAULT_CSV):
    """Yield normalized dicts from a rankings CSV file path."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        yield from parse_reader(csv.DictReader(f))


def parse_text(text):
    """Yield normalized dicts from raw CSV text (e.g. an uploaded file)."""
    import io
    yield from parse_reader(csv.DictReader(io.StringIO(text)))


def import_rows(db: Session, rows, source=DEFAULT_SOURCE):
    """
    Upsert an iterable of normalized rows into player_rankings under `source`.
    Returns {"imported": n_new, "updated": n_existing, "total": n_in_source}.
    """
    imported = 0
    updated = 0
    for data in rows:
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


def import_rankings(db: Session, path=DEFAULT_CSV, source=DEFAULT_SOURCE):
    """Upsert rows from a CSV file `path` into player_rankings under `source`."""
    return import_rows(db, parse_rows(path), source)


def import_text(db: Session, text, source=DEFAULT_SOURCE):
    """Upsert rows from raw CSV `text` into player_rankings under `source`."""
    return import_rows(db, parse_text(text), source)


EXPERT_SOURCE = "Expert Consensus PPR Redraft 2026"


def build_expert_source(db: Session, base_source=DEFAULT_SOURCE, expert_source=EXPERT_SOURCE):
    """
    Derive a standalone source ranked by the Expert Rank column of `base_source`.

    Players are re-ordered by expert_rank (ascending) and given a fresh 1..N
    overall rank. Tier bands are carried over from the base source's own tier
    sizes applied in expert order (top block = S, next = A, …), so the tier
    filter stays meaningful. The original Mason Dodd rank is preserved for
    side-by-side comparison. Rebuilt from scratch each call (idempotent).
    """
    base_rows = (
        db.query(PlayerRanking)
        .filter(PlayerRanking.source == base_source)
        .order_by(PlayerRanking.rank.asc())
        .all()
    )
    ranked = [r for r in base_rows if r.expert_rank is not None]
    if not ranked:
        return {"imported": 0, "total": 0}

    # Tier labels in base-rank order (band sizes to reuse for the expert board).
    tier_sequence = [r.tier for r in ranked]
    expert_order = sorted(ranked, key=lambda r: r.expert_rank)

    # Rebuild the expert source cleanly.
    db.query(PlayerRanking).filter(PlayerRanking.source == expert_source).delete(
        synchronize_session=False
    )
    for i, r in enumerate(expert_order):
        db.add(PlayerRanking(
            source=expert_source,
            player_id=r.player_id,
            rank=i + 1,
            name=r.name,
            team=r.team,
            position=r.position,
            tier=tier_sequence[i] if i < len(tier_sequence) else None,
            mason_dodd_rank=r.mason_dodd_rank,
            expert_rank=r.expert_rank,
        ))
    db.commit()
    total = db.query(PlayerRanking).filter(PlayerRanking.source == expert_source).count()
    return {"imported": len(expert_order), "total": total}


def ensure_expert_source(db: Session):
    """Create the derived Expert source if the base exists and it's missing."""
    has_base = db.query(PlayerRanking).filter(PlayerRanking.source == DEFAULT_SOURCE).first()
    has_expert = db.query(PlayerRanking).filter(PlayerRanking.source == EXPERT_SOURCE).first()
    if has_base and not has_expert:
        build_expert_source(db, DEFAULT_SOURCE, EXPERT_SOURCE)


# Old source labels that predate the current names, mapped to what they're now.
LEGACY_SOURCE_RENAMES = {"REDRAFT PPR": DEFAULT_SOURCE}


def migrate_legacy_source_names(db: Session):
    """
    Rename known legacy source labels to their current names on existing
    databases (idempotent). This is why a DB first seeded as "REDRAFT PPR"
    shows up as "Mason Dodd PPR Redraft 2026" after upgrading, without a reseed.
    """
    changed = False
    for old, new in LEGACY_SOURCE_RENAMES.items():
        if old == new:
            continue
        has_old = db.query(PlayerRanking).filter(PlayerRanking.source == old).first()
        has_new = db.query(PlayerRanking).filter(PlayerRanking.source == new).first()
        if has_old and not has_new:
            db.query(PlayerRanking).filter(PlayerRanking.source == old).update(
                {PlayerRanking.source: new}, synchronize_session=False
            )
            changed = True
    if changed:
        db.commit()


def seed_rankings(db: Session):
    """Load the bundled rankings on first run, migrate legacy names, derive Expert."""
    migrate_legacy_source_names(db)
    if os.path.exists(DEFAULT_CSV) and (
        db.query(PlayerRanking).filter(PlayerRanking.source == DEFAULT_SOURCE).count() == 0
    ):
        import_rankings(db, DEFAULT_CSV, DEFAULT_SOURCE)
    ensure_expert_source(db)
