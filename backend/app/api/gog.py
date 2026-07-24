"""GOG library import — see core/library_import.py for the mechanics."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.library_import import StoreSpec, fetch_covers, import_library
from app.core.security import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.library_import import LibraryImportOut

router = APIRouter(prefix="/api/gog", tags=["gog"])

GOG = StoreSpec(
    runner="gog",
    id_key="gog_product_id",
    storefront="GOG",
    event_source="gog_import",
    file_hint="Heroic's store_cache/gog_library.json",
)


@router.post("/import", response_model=LibraryImportOut)
async def import_gog_library(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LibraryImportOut:
    """Bulk-create digital game items from an uploaded GOG library file.

    Covers are fetched in a background task so importing a large library
    responds quickly; posters fill in shortly after.
    """
    raw = await file.read()
    imported_ids, total = import_library(db, user, raw, GOG)
    if imported_ids:
        background.add_task(fetch_covers, imported_ids)
    return LibraryImportOut(
        imported=len(imported_ids), skipped=total - len(imported_ids), total=total
    )
