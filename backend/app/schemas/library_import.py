from pydantic import BaseModel


class LibraryImportOut(BaseModel):
    imported: int
    skipped: int
    total: int
