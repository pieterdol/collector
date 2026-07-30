from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core import vision
from app.core.barcodes import clean_code, find_owned
from app.core.security import get_current_user
from app.db import get_db
from app.domain.enums import ItemType
from app.models import User
from app.providers import all_providers, get_provider
from app.schemas.enrich import BarcodeOut, EnrichSearchOut, PhotoReadOut, ProvidersOut

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
    user: User = Depends(get_current_user),
) -> BarcodeOut:
    """ISBN → Open Library; other UPC/EAN codes → the music catalogs, which
    index sleeve barcodes. Discs and game boxes have no public barcode
    catalog: their code is returned for storage and the UI offers title
    search instead.

    A code the user already has short-circuits all of that: the item id
    comes back so the scanner can open it instead of adding a second copy.
    """
    clean = clean_code(code)
    owned = find_owned(db, user.id, clean, isbn=_is_isbn(clean))
    if owned is not None:
        return BarcodeOut(
            code=clean,
            kind="isbn" if _is_isbn(clean) else "upc",
            matched=False,
            owned_item_id=owned.id,
        )
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


@router.post("/photo", response_model=PhotoReadOut)
async def photo(
    type: ItemType,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> PhotoReadOut:
    """Read a title off a photographed cover — the answer for discs and game
    boxes, which no barcode catalog covers.

    Both vision models are asked and every answer is treated as a guess: the
    catalog search is what confirms one. When none of them lands, whatever
    was read still comes back, so the search box starts from a near-miss
    instead of empty.
    """
    if not vision.available():
        raise HTTPException(status_code=503, detail="Cover reading is not configured")
    provider = get_provider(type, db)
    try:
        image = vision.prepare_image(await file.read())
    except OSError:
        raise HTTPException(status_code=415, detail="That file isn't an image") from None

    try:
        lines = vision.read_cover(image)
    except vision.VisionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # One read gives all three: the console narrows a game search to the
    # edition in your hands, the rest are search terms for the title.
    console = vision.platform_from(lines) if type is ItemType.GAME else None
    candidates = vision.candidates_from(lines)
    query, platform = _first_with_results(provider, candidates, console)
    # A console that didn't narrow to a hit is dropped, because the UI re-runs
    # this search with the platform preselected and a misread one would filter
    # it down to nothing. With no hit at all there's nothing to contradict it,
    # so it stays as a hint for the search the user is about to fix by hand.
    return PhotoReadOut(read=candidates, query=query, platform=platform if query else console)


def _first_with_results(
    provider, candidates: list[str], platform: str | None
) -> tuple[str | None, str | None]:
    """The first candidate the catalog knows, plus the platform that found it.

    A console read off the box is a guess like any other, so it is only kept
    when it actually narrowed to a hit: the UI re-runs this search with the
    platform preselected, and a misread console would filter that down to
    nothing. Repeats are cheap — provider lookups are cached.
    """
    if not provider.available:
        return None, None
    narrows = bool(platform) and provider.supports_platform_filter
    for candidate in candidates:
        if len(candidate) < 2:
            continue
        if narrows and provider.search(candidate, platform=platform):
            return candidate, platform
        if provider.search(candidate):
            return candidate, None
    return None, None


@router.get("/providers", response_model=ProvidersOut)
def providers(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ProvidersOut:
    return ProvidersOut(
        providers=[
            {"name": p.name, "type": p.item_type, "available": p.available}
            for p in all_providers(db)
        ],
        vision=vision.available(),
    )
