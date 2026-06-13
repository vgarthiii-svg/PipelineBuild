from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card, STATUS_IN_STOCK, STATUS_LISTED, STATUS_SOLD

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _sum(db, column, *filters):
    q = db.query(func.coalesce(func.sum(column), 0.0))
    for f in filters:
        q = q.filter(f)
    return q.scalar() or 0.0


@router.get("")
def dashboard(db: Session = Depends(get_db)):
    """Summary stats for the inventory dashboard, including sales P&L."""
    total = db.query(func.count(Card.id)).scalar() or 0

    by_status = {STATUS_IN_STOCK: 0, STATUS_LISTED: 0, STATUS_SOLD: 0}
    for status, count in db.query(Card.status, func.count(Card.id)).group_by(Card.status):
        by_status[status] = count

    unsold = (Card.status != STATUS_SOLD)
    sold = (Card.status == STATUS_SOLD)

    # Money tied up in unsold inventory (cost basis of cards on hand)
    inventory_cost = _sum(db, Card.purchase_price, unsold)

    # Sales P&L
    revenue = _sum(db, Card.sale_price, sold)
    cost_of_sold = _sum(db, Card.purchase_price, sold)
    fees = _sum(db, Card.sale_fees, sold) + _sum(db, Card.sale_shipping, sold)
    net_profit = revenue - cost_of_sold - fees
    roi = (net_profit / cost_of_sold * 100.0) if cost_of_sold > 0 else 0.0

    total_spent = _sum(db, Card.purchase_price)  # all cards, sold or not

    by_sport = [
        {"sport": sport or "Unknown", "count": count}
        for sport, count in db.query(Card.sport, func.count(Card.id))
        .group_by(Card.sport)
        .order_by(func.count(Card.id).desc())
        .all()
    ]

    recent = [
        {
            "id": c.id, "card_id": c.card_id, "player": c.player, "sport": c.sport,
            "status": c.status, "sale_price": c.sale_price, "purchase_price": c.purchase_price,
            "front_image": c.front_image,
        }
        for c in db.query(Card).order_by(Card.id.desc()).limit(5).all()
    ]

    return {
        "total_cards": total,
        "by_status": by_status,
        "inventory_cost": round(inventory_cost, 2),
        "total_spent": round(total_spent, 2),
        "revenue": round(revenue, 2),
        "cost_of_sold": round(cost_of_sold, 2),
        "fees": round(fees, 2),
        "net_profit": round(net_profit, 2),
        "roi": round(roi, 1),
        "by_sport": by_sport,
        "recent": recent,
    }
