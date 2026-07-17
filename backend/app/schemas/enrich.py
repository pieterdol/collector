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


class ProviderStatus(BaseModel):
    name: str
    type: ItemType
    available: bool


class ProvidersOut(BaseModel):
    providers: list[ProviderStatus]
