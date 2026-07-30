import uuid

from pydantic import BaseModel

from app.domain.enums import ItemType


class EnrichResult(BaseModel):
    title: str
    type: ItemType
    metadata: dict
    cover_url: str | None
    external_id: str | None


class EnrichSearchOut(BaseModel):
    provider: str
    available: bool
    results: list[EnrichResult]


class BarcodeOut(BaseModel):
    code: str
    kind: str  # "isbn" | "upc"
    matched: bool
    result: EnrichResult | None = None
    #: Set when the code is already in the user's collection. The catalog is
    #: not asked in that case, so `matched`/`result` say nothing — check this
    #: first and open the item instead of adding a duplicate.
    owned_item_id: uuid.UUID | None = None


class PhotoReadOut(BaseModel):
    """What a photographed cover yielded. Search terms, not metadata."""

    #: Every candidate the models offered, best first — shown to the user so
    #: a partial read ("BLADE") is one word away from being fixed.
    read: list[str]
    #: The candidate the catalog recognised; None when none of them hit.
    query: str | None = None
    #: Console printed on the box, when the models saw one.
    platform: str | None = None


class ProviderStatus(BaseModel):
    name: str
    type: ItemType
    available: bool


class ProvidersOut(BaseModel):
    providers: list[ProviderStatus]
    #: Whether a local vision model is configured (see core/vision.py).
    vision: bool = False
