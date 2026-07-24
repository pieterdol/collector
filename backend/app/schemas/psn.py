from pydantic import BaseModel


class PsnJobStartOut(BaseModel):
    job_id: str


class PsnJobOut(BaseModel):
    status: str  # running | done | error
    phase: str
    done: int = 0
    total: int = 0
    imported: int | None = None
    skipped: int | None = None
    detail: str | None = None
