from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, Text

from app.database import Base

# Card lifecycle statuses
STATUS_IN_STOCK = "in_stock"
STATUS_LISTED = "listed"
STATUS_SOLD = "sold"
VALID_STATUSES = (STATUS_IN_STOCK, STATUS_LISTED, STATUS_SOLD)


class Card(Base):
    """A single physical sports card in the inventory."""

    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    # Human-facing inventory id, e.g. INV-0001
    card_id = Column(String, unique=True, index=True, nullable=False)

    # Identity (extracted from the card photos by Claude Vision, editable)
    player = Column(String, default="")
    year = Column(String, default="")
    brand = Column(String, default="")        # manufacturer, e.g. Topps, Panini
    set_name = Column(String, default="")     # set, e.g. Chrome, Prizm
    card_number = Column(String, default="")
    variation = Column(String, default="")    # parallel / insert / refractor
    team = Column(String, default="")
    sport = Column(String, default="")
    is_rookie = Column(String, default="")    # "yes" / "no" / "" (kept as text for simplicity)
    condition = Column(String, default="")
    notes = Column(Text, default="")

    # Workflow
    status = Column(String, default=STATUS_IN_STOCK, index=True)

    # Images (filenames stored under data/images, served from /images/<name>)
    front_image = Column(String, default="")
    back_image = Column(String, default="")

    # Financials (populated in later phases; defined now so the schema is stable)
    purchase_price = Column(Float, nullable=True)  # cost basis
    sale_price = Column(Float, nullable=True)
    estimated_value = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
