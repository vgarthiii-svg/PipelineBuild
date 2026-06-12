from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey

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

    # Financials
    purchase_price = Column(Float, nullable=True)  # cost basis
    estimated_value = Column(Float, nullable=True)

    # Purchase (acquisition) details
    purchase_date = Column(String, default="")
    purchase_source = Column(String, default="")  # eBay, card show, breaker, lot...

    # Sale details
    sale_price = Column(Float, nullable=True)
    sale_date = Column(String, default="")
    sale_platform = Column(String, default="")    # eBay, COMC, in person...
    sale_fees = Column(Float, nullable=True)       # marketplace/payment fees
    sale_shipping = Column(Float, nullable=True)   # shipping cost paid by seller
    sale_notes = Column(Text, default="")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def net_profit(self):
        """Profit on a sold card: sale - cost basis - fees - shipping."""
        if self.sale_price is None:
            return None
        return round(
            (self.sale_price or 0.0)
            - (self.purchase_price or 0.0)
            - (self.sale_fees or 0.0)
            - (self.sale_shipping or 0.0),
            2,
        )


class ChecklistSet(Base):
    """A set checklist, e.g. '2023 Topps Chrome' with N cards to collect."""

    __tablename__ = "checklist_sets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)   # e.g. "Chrome"
    year = Column(String, default="")
    brand = Column(String, default="")      # e.g. "Topps"
    sport = Column(String, default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class ChecklistItem(Base):
    """A single card entry within a checklist set, with an owned flag."""

    __tablename__ = "checklist_items"

    id = Column(Integer, primary_key=True, index=True)
    set_id = Column(Integer, ForeignKey("checklist_sets.id"), index=True, nullable=False)
    card_number = Column(String, default="")
    player = Column(String, default="")
    variation = Column(String, default="")
    owned = Column(Boolean, default=False)
    notes = Column(String, default="")
