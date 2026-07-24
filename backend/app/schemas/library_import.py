from pydantic import BaseModel, Field


class JobStartOut(BaseModel):
    job_id: str


class ReviewTitle(BaseModel):
    """One entitlement awaiting the user's verdict."""

    title_id: str
    name: str
    platform: str | None = None
    subscription: str | None = None
    # Why the auto-filter excluded it (excluded list only).
    reason: str | None = None
    # Informational note on a candidate, e.g. the same game owned on
    # another platform — worth knowing, not a reason to skip.
    note: str | None = None


class ImportJobOut(BaseModel):
    status: str  # running | review | done | error
    phase: str
    done: int = 0
    total: int = 0
    imported: int | None = None
    skipped: int | None = None
    detail: str | None = None
    # Populated while status == "review".
    candidates: list[ReviewTitle] | None = None
    excluded: list[ReviewTitle] | None = None


class ConfirmIn(BaseModel):
    title_ids: list[str] = Field(max_length=5000)


# Legacy aliases: the PSN router named these first.
PsnJobStartOut = JobStartOut
PsnJobOut = ImportJobOut
PsnConfirmIn = ConfirmIn
PsnReviewTitle = ReviewTitle
