from pydantic import BaseModel, Field


class SteamImportIn(BaseModel):
    # SteamID64 ("7656119…") or vanity name / profile URL.
    steam_id: str = Field(min_length=2, max_length=200)


class SteamImportOut(BaseModel):
    imported: int
    skipped: int
    total: int
