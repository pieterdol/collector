"""Matching a scanned barcode against what the user already has.

Scanning a code that is already in the collection should open that item, not
start a second copy of it — so the barcode endpoint asks here first, and a
hit skips the catalog lookup entirely.
"""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Item

#: Metadata keys a code can be stored under: books keep the ISBN they were
#: looked up by, records the sleeve barcode the catalog reported, and a scan
#: with no catalog match (movies, games) keeps the raw code as `upc`.
CODE_FIELDS = ("isbn", "upc", "barcode")


def clean_code(code: str) -> str:
    """Codes are printed, scanned and typed with dashes and spaces."""
    return code.replace("-", "").replace(" ", "")


def isbn_variants(code: str) -> list[str]:
    """Both ISBN forms of one edition.

    The barcode on a book is its ISBN-13, but an item added by title search
    often carries the ISBN-10 the catalog listed — the same edition under a
    second name, so a scan has to try both. (979-prefixed ISBN-13s have no
    ISBN-10 equivalent.)
    """
    if len(code) == 13 and code.startswith("978"):
        core = code[3:12]
        return [code, core + _isbn10_check(core)]
    if len(code) == 10:
        thirteen = "978" + code[:9]
        return [code, thirteen + _ean13_check(thirteen)]
    return [code]


def find_owned(db: Session, user_id: uuid.UUID, code: str, isbn: bool) -> Item | None:
    """The user's item carrying this code, if they already added it."""
    codes = isbn_variants(code) if isbn else [code]
    stored = [
        # Stored codes keep whatever punctuation their source used.
        func.replace(func.replace(Item.meta[field].astext, "-", ""), " ", "")
        for field in CODE_FIELDS
    ]
    return db.scalars(
        select(Item)
        .where(Item.user_id == user_id, or_(*[column.in_(codes) for column in stored]))
        # Oldest first: the copy that has been on the shelf is the one to open.
        .order_by(Item.created_at)
        .limit(1)
    ).first()


def _isbn10_check(core: str) -> str:
    total = sum((10 - i) * int(digit) for i, digit in enumerate(core))
    check = (11 - total % 11) % 11
    return "X" if check == 10 else str(check)


def _ean13_check(core: str) -> str:
    total = sum(int(digit) * (3 if i % 2 else 1) for i, digit in enumerate(core))
    return str((10 - total % 10) % 10)
