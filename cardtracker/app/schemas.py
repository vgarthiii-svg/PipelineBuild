from typing import Optional

from pydantic import BaseModel, field_validator


class _StrSafe(BaseModel):
    """Coerce NULL/None into '' for plain string fields (defensive against
    legacy rows that may hold NULLs in text columns)."""

    @field_validator("*", mode="before")
    @classmethod
    def _none_to_empty(cls, v, info):
        if v is None and cls.model_fields[info.field_name].annotation is str:
            return ""
        return v


class CardFields(_StrSafe):
    """The editable identity fields of a card (what scanning extracts / the user edits)."""

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
    """Payload for creating a card. Image filenames come from the upload step."""

    front_image: str = ""
    back_image: str = ""
    status: str = "in_stock"
    purchase_price: Optional[float] = None
    estimated_value: Optional[float] = None
    purchase_date: str = ""
    purchase_source: str = ""


class CardUpdate(CardFields):
    status: Optional[str] = None
    purchase_price: Optional[float] = None
    estimated_value: Optional[float] = None
    purchase_date: Optional[str] = None
    purchase_source: Optional[str] = None
    # Sale details
    sale_price: Optional[float] = None
    sale_date: Optional[str] = None
    sale_platform: Optional[str] = None
    sale_fees: Optional[float] = None
    sale_shipping: Optional[float] = None
    sale_notes: Optional[str] = None


class CardOut(CardCreate):
    id: int
    card_id: str
    sale_price: Optional[float] = None
    sale_date: str = ""
    sale_platform: str = ""
    sale_fees: Optional[float] = None
    sale_shipping: Optional[float] = None
    sale_notes: str = ""
    net_profit: Optional[float] = None

    class Config:
        from_attributes = True


class UploadResult(BaseModel):
    """Returned by /api/cards/upload: stored image filenames (no AI, no cost)."""

    front_image: str
    back_image: str


class ExtractResult(BaseModel):
    """Returned by /api/cards/extract (optional paid Claude Vision path)."""

    front_image: str
    back_image: str
    extracted: CardFields
    vision_used: bool
    message: str = ""


# ---------- Checklists ----------

class ChecklistSetCreate(_StrSafe):
    name: str = ""
    year: str = ""
    brand: str = ""
    sport: str = ""
    notes: str = ""


class ChecklistSetUpdate(_StrSafe):
    name: Optional[str] = None
    year: Optional[str] = None
    brand: Optional[str] = None
    sport: Optional[str] = None
    notes: Optional[str] = None


class ChecklistItemIn(_StrSafe):
    card_number: str = ""
    player: str = ""
    variation: str = ""
    owned: bool = False
    notes: str = ""


class ChecklistItemOut(ChecklistItemIn):
    id: int
    set_id: int

    class Config:
        from_attributes = True


class ChecklistSetOut(ChecklistSetCreate):
    id: int
    total_items: int = 0
    owned_items: int = 0
    pct_complete: float = 0.0

    class Config:
        from_attributes = True
