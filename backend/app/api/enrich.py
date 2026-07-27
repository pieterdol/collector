from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.domain.enums import ItemType
from app.models import User
from app.providers import all_providers, get_provider
from app.schemas.enrich import BarcodeOut, EnrichSearchOut, ProvidersOut

router = APIRouter(prefix="/api/enrich", tags=["enrich"])


def _is_isbn(code: str) -> bool:
    digits = code.replace("-", "").replace(" ", "")
    if len(digits) == 10:
        return digits[:9].isdigit()
    return len(digits) == 13 and digits.isdigit() and digits.startswith(("978", "979"))


@router.get("/search", response_model=EnrichSearchOut)
def search(
    type: ItemType,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    platform: Annotated[str | None, Query(max_length=100)] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> EnrichSearchOut:
    """Catalog search. `platform` narrows game results (IGDB); other
    providers have nothing to narrow, so they ignore it."""
    provider = get_provider(type, db)
    if not provider.available:
        results = []
    elif platform and provider.supports_platform_filter:
        results = provider.search(q, platform=platform)
    else:
        results = provider.search(q)
    return EnrichSearchOut(
        provider=provider.name,
        available=provider.available,
        results=[r.as_dict() for r in results],
    )


@router.get("/details", response_model=EnrichSearchOut)
def details(
    type: ItemType,
    external_id: Annotated[str, Query(min_length=1, max_length=50)],
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> EnrichSearchOut:
    """Richer record for one picked result (e.g. TMDB adds director/runtime)."""
    provider = get_provider(type, db)
    if not provider.available:
        raise HTTPException(status_code=503, detail=f"{provider.name} is not configured")
    result = provider.details(external_id)
    return EnrichSearchOut(
        provider=provider.name,
        available=True,
        results=[result.as_dict()] if result else [],
    )


@router.get("/barcode", response_model=BarcodeOut)
def barcode(
    code: Annotated[str, Query(min_length=8, max_length=20)],
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> BarcodeOut:
    """ISBN → Open Library; other UPC/EAN codes → the music catalogs, which
    index sleeve barcodes. Discs and game boxes have no public barcode
    catalog: their code is returned for storage and the UI offers title
    search instead."""
    clean = code.replace("-", "").replace(" ", "")
    if _is_isbn(clean):
        result = get_provider(ItemType.BOOK, db).lookup_barcode(clean)
        return BarcodeOut(
            code=clean,
            kind="isbn",
            matched=result is not None,
            result=result.as_dict() if result else None,
        )
    music = get_provider(ItemType.MUSIC, db).lookup_barcode(clean)
    return BarcodeOut(
        code=clean,
        kind="upc",
        matched=music is not None,
        result=music.as_dict() if music else None,
    )


@router.get("/providers", response_model=ProvidersOut)
def providers(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ProvidersOut:
    return ProvidersOut(
        providers=[
            {"name": p.name, "type": p.item_type, "available": p.available}
            for p in all_providers(db)
        ]
    )
