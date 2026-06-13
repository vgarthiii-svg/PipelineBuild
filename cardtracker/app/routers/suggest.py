"""
Autocomplete suggestions drawn from the user's own data (inventory cards +
checklist sets/items) plus built-in brand/set/team lists. Powers the
type-ahead in the add/edit forms so spellings are consistent and picking a
player can auto-fill their team, sport, year, set, etc.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card, ChecklistSet, ChecklistItem

router = APIRouter(prefix="/api/suggest", tags=["suggest"])

BRANDS = ["Topps", "Panini", "Bowman", "Upper Deck", "Fleer", "Donruss", "Score", "Leaf"]
SETS = [
    "Chrome", "Prizm", "Select", "Mosaic", "Optic", "Stadium Club", "Heritage",
    "Finest", "Allen & Ginter", "Gallery", "Contenders", "Chronicles", "Sapphire",
    "Gypsy Queen", "Big League", "Inception", "Obsidian", "National Treasures",
    "Flawless", "Immaculate", "Hoops", "Revolution", "Update", "Archives", "Series 1", "Series 2",
]
TEAMS = {
    "Baseball": ["Diamondbacks", "Braves", "Orioles", "Red Sox", "Cubs", "White Sox", "Reds", "Guardians", "Rockies", "Tigers", "Astros", "Royals", "Angels", "Dodgers", "Marlins", "Brewers", "Twins", "Mets", "Yankees", "Athletics", "Phillies", "Pirates", "Padres", "Giants", "Mariners", "Cardinals", "Rays", "Rangers", "Blue Jays", "Nationals"],
    "Basketball": ["Hawks", "Celtics", "Nets", "Hornets", "Bulls", "Cavaliers", "Mavericks", "Nuggets", "Pistons", "Warriors", "Rockets", "Pacers", "Clippers", "Lakers", "Grizzlies", "Heat", "Bucks", "Timberwolves", "Pelicans", "Knicks", "Thunder", "Magic", "76ers", "Suns", "Trail Blazers", "Kings", "Spurs", "Raptors", "Jazz", "Wizards"],
    "Football": ["Cardinals", "Falcons", "Ravens", "Bills", "Panthers", "Bears", "Bengals", "Browns", "Cowboys", "Broncos", "Lions", "Packers", "Texans", "Colts", "Jaguars", "Chiefs", "Raiders", "Chargers", "Rams", "Dolphins", "Vikings", "Patriots", "Saints", "Giants", "Jets", "Eagles", "Steelers", "49ers", "Seahawks", "Buccaneers", "Commanders", "Titans"],
    "Hockey": ["Ducks", "Bruins", "Sabres", "Flames", "Hurricanes", "Blackhawks", "Avalanche", "Blue Jackets", "Stars", "Red Wings", "Oilers", "Panthers", "Wild", "Canadiens", "Predators", "Devils", "Islanders", "Senators", "Flyers", "Penguins", "Sharks", "Kraken", "Blues", "Lightning", "Maple Leafs", "Canucks", "Golden Knights", "Capitals", "Coyotes"],
}
SPORT_BY_TEAM = {t.lower(): sport for sport, teams in TEAMS.items() for t in teams}

_VALID = {"player", "team", "brand", "set_name", "year", "card_number"}


def _records(db: Session):
    """Flatten inventory cards and checklist items into comparable records."""
    recs = []
    for c in db.query(Card).all():
        recs.append({
            "player": c.player or "", "team": c.team or "", "sport": c.sport or "",
            "year": c.year or "", "brand": c.brand or "", "set_name": c.set_name or "",
            "card_number": c.card_number or "",
        })
    rows = (
        db.query(ChecklistItem, ChecklistSet)
        .join(ChecklistSet, ChecklistItem.set_id == ChecklistSet.id)
        .all()
    )
    for it, s in rows:
        recs.append({
            "player": it.player or "", "team": "", "sport": s.sport or "",
            "year": s.year or "", "brand": s.brand or "", "set_name": s.name or "",
            "card_number": it.card_number or "",
        })
    return recs


@router.get("")
def suggest(
    field: str,
    q: str = "",
    player: str = "",
    set_name: str = "",
    db: Session = Depends(get_db),
):
    if field not in _VALID:
        return []
    ql = q.strip().lower()
    recs = _records(db)
    out, seen = [], set()

    def add(value, fill):
        v = (value or "").strip()
        if not v or v.lower() in seen:
            return
        seen.add(v.lower())
        out.append({"value": v, "fill": {k: val for k, val in (fill or {}).items() if val}})

    if field == "player":
        rep = {}
        for r in recs:
            p = r["player"].strip()
            if not p or (ql and ql not in p.lower()):
                continue
            # First record wins; inventory is added before checklists, so it
            # provides the team when available.
            if p not in rep or (not rep[p].get("team") and r.get("team")):
                rep[p] = r
        for p, r in rep.items():
            add(p, {k: r.get(k, "") for k in ("team", "sport", "year", "brand", "set_name")})

    elif field == "team":
        for sport, teams in TEAMS.items():
            for t in teams:
                if not ql or ql in t.lower():
                    add(t, {"sport": sport})
        for r in recs:
            t = r["team"].strip()
            if t and (not ql or ql in t.lower()):
                add(t, {"sport": r.get("sport") or SPORT_BY_TEAM.get(t.lower(), "")})

    elif field in ("brand", "set_name"):
        for v in (BRANDS if field == "brand" else SETS):
            if not ql or ql in v.lower():
                add(v, {})
        for r in recs:
            v = r[field].strip()
            if v and (not ql or ql in v.lower()):
                add(v, {})

    elif field == "year":
        for r in recs:
            v = r["year"].strip()
            if v and (not ql or v.lower().startswith(ql)):
                add(v, {})

    elif field == "card_number":
        for r in recs:
            v = r["card_number"].strip()
            if not v:
                continue
            if set_name and r["set_name"].lower() != set_name.lower():
                continue
            if player and r["player"].lower() != player.lower():
                continue
            if not ql or ql in v.lower():
                add(v, {"player": r.get("player", ""), "set_name": r.get("set_name", "")})

    out.sort(key=lambda x: x["value"].lower())
    return out[:8]
