from pydantic import BaseModel, Field


class PsnJobStartOut(BaseModel):
    job_id: str


class PsnReviewTitle(BaseModel):
    title_id: str
    name: str
    platform: str | None = None
    subscription: str | None = None
    # Why the auto-filter excluded it (excluded list only).
    reason: str | None = None


class PsnJobOut(BaseModel):
    status: str  # running | review | done | error
    phase: str
    done: int = 0
    total: int = 0
    imported: int | None = None
    skipped: int | None = None
    detail: str | None = None
    # Populated while status == "review".
    candidates: list[PsnReviewTitle] | None = None
    excluded: list[PsnReviewTitle] | None = None


class PsnConfirmIn(BaseModel):
    title_ids: list[str] = Field(max_length=5000)
