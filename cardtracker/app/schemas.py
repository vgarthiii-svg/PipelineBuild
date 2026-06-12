from typing import Optional

from pydantic import BaseModel


class CardFields(BaseModel):
    """The editable identity fields of a card (what Vision extracts / the user edits)."""

    player: str = ""
    year: str = ""
    brand: str = ""
    set_name: str = ""
    card_number: str = ""
    variation: str = ""
    team: str = ""
    sport: str = ""
    is_rookie: str = ""
    condition: str = ""
    notes: str = ""


class CardCreate(CardFields):
    """Payload for creating a card. Image filenames come from the /extract step."""

    front_image: str = ""
    back_image: str = ""
    status: str = "in_stock"
    purchase_price: Optional[float] = None
    estimated_value: Optional[float] = None


class CardUpdate(CardFields):
    status: Optional[str] = None
    purchase_price: Optional[float] = None
    sale_price: Optional[float] = None
    estimated_value: Optional[float] = None


class CardOut(CardCreate):
    id: int
    card_id: str
    sale_price: Optional[float] = None

    class Config:
        from_attributes = True


class ExtractResult(BaseModel):
    """Returned by /api/cards/extract: stored image names + Vision-extracted fields."""

    front_image: str
    back_image: str
    extracted: CardFields
    vision_used: bool
    message: str = ""
