from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card, STATUS_IN_STOCK, STATUS_LISTED, STATUS_SOLD

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(db: Session = Depends(get_db)):
    """Summary stats for the inventory dashboard."""
    total = db.query(func.count(Card.id)).scalar() or 0

    by_status = {
        STATUS_IN_STOCK: 0,
        STATUS_LISTED: 0,
        STATUS_SOLD: 0,
    }
    for status, count in db.query(Card.status, func.count(Card.id)).group_by(Card.status):
        by_status[status] = count

    cost_basis = db.query(func.coalesce(func.sum(Card.purchase_price), 0.0)).scalar() or 0.0
    revenue = (
        db.query(func.coalesce(func.sum(Card.sale_price), 0.0))
        .filter(Card.status == STATUS_SOLD)
        .scalar()
        or 0.0
    )
    # Profit on sold cards: sale - cost basis for cards that have both
    profit = (
        db.query(
            func.coalesce(
                func.sum(func.coalesce(Card.sale_price, 0.0) - func.coalesce(Card.purchase_price, 0.0)),
                0.0,
            )
        )
        .filter(Card.status == STATUS_SOLD)
        .scalar()
        or 0.0
    )

    by_sport = [
        {"sport": sport or "Unknown", "count": count}
        for sport, count in db.query(Card.sport, func.count(Card.id))
        .group_by(Card.sport)
        .order_by(func.count(Card.id).desc())
        .all()
    ]

    return {
        "total_cards": total,
        "by_status": by_status,
        "cost_basis": round(cost_basis, 2),
        "revenue": round(revenue, 2),
        "profit": round(profit, 2),
        "by_sport": by_sport,
    }
