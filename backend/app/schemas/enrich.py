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


class ProviderStatus(BaseModel):
    name: str
    type: ItemType
    available: bool


class ProvidersOut(BaseModel):
    providers: list[ProviderStatus]
