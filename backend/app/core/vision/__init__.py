"""Reading a cover with a vision model.

Movie discs and game boxes have no public barcode catalog, so the fallback used
to be "type the title yourself". A photo of the front answers that instead —
but only as a *search term*: nothing here is trusted, it is handed to the
normal catalog search and the catalog decides which reading was real.

One call per photo returns every line printed on the box, from which the title,
the console and the publisher all fall out (see base.ALL_TEXT_PROMPT for why
asking for the title directly is a trap).

**Adding a backend** — e.g. Claude — is one new module implementing
`VisionBackend.read_lines` plus one entry in `_BACKENDS` below. Nothing else in
this package or its callers changes: the ordering, noise filtering, console
detection and candidate building are all backend-agnostic.
"""

import re

from app.config import get_settings
from app.core.vision.base import (
    MAX_EDGE,
    VisionBackend,
    VisionUnavailable,
    prepare_image,
)
from app.core.vision.gemini import GeminiBackend
from app.core.vision.ollama import OllamaBackend

__all__ = [
    "MAX_EDGE",
    "NOISE",
    "PLATFORMS",
    "VisionBackend",
    "VisionUnavailable",
    "available",
    "backends",
    "candidates_from",
    "dedupe",
    "platform_from",
    "prepare_image",
    "read_cover",
    "search_terms",
]

#: Every backend that exists. VISION_BACKENDS picks which ones run, and in
#: what order — the first that answers with anything wins.
_BACKENDS: dict[str, type[VisionBackend]] = {
    "gemini": GeminiBackend,
    "ollama": OllamaBackend,
}

#: Printed on nearly every box and never worth searching for.
NOISE = re.compile(
    r"^\W*(?:"
    r"(?:www\.|https?://).*"
    r"|(?:pegi|usk|esrb|cero)\b.*"
    r"|\d{1,2}\+?"  # a bare rating number ("18"); real years survive
    r"|ultra\s?hd|blu-?ray|dvd|4k"
    r"|only\son\splaystation"
    r"|includes\b.*voucher.*"
    r"|(?:ultimate|deluxe|standard|collector'?s)\sedition"
    r"|game\sof\sthe\syear.*"
    r"|tm|\(r\)"
    r")\W*$",
    re.IGNORECASE,
)

#: Console as printed on the box → the platform name IGDB uses. Keys are
#: normalised by _platform_key, so punctuation and spacing don't matter
#: ("PS5.", "PlayStation®5" and "playstation 5" all land here).
PLATFORMS = {
    "ps5": "PlayStation 5",
    "playstation5": "PlayStation 5",
    "ps4": "PlayStation 4",
    "playstation4": "PlayStation 4",
    "nintendoswitch2": "Nintendo Switch 2",
    "nintendoswitch": "Nintendo Switch",
    "xboxseriesx|s": "Xbox Series X|S",
    "xboxseriesxs": "Xbox Series X|S",
    "xboxseriesx": "Xbox Series X|S",
    "xboxone": "Xbox One",
    "xbox360": "Xbox 360",
    # Last, and bare on purpose: the original console's box prints just the
    # wordmark. Every later Xbox qualifies it and lookup is on the whole
    # line, so this key can't swallow them — nor "XBOX GAME STUDIOS", the
    # publisher line printed on the boxes that do say plain "XBOX".
    "xbox": "Xbox",
}


def backends() -> list[VisionBackend]:
    """The configured backends, in the order they should be tried."""
    wanted = [name.strip() for name in get_settings().vision_backends.split(",")]
    chosen = [_BACKENDS[name]() for name in wanted if name in _BACKENDS]
    return [backend for backend in chosen if backend.available()]


def available() -> bool:
    return bool(backends())


def read_cover(image: bytes) -> list[str]:
    """Every line printed on the box, noise removed.

    Backends are tried in order and a failure is not fatal: a throttled cloud
    model, or one that answered but saw nothing, falls through to the next
    (in practice: Gemini's free tier sheds load, the local model catches it).
    """
    candidates = backends()
    if not candidates:
        raise VisionUnavailable("Cover reading is not configured")
    failure: VisionUnavailable | None = None
    for backend in candidates:
        try:
            lines = _clean(backend.read_lines(image))
        except VisionUnavailable as exc:
            failure = exc
            continue
        if lines:
            return lines
    if failure is not None:
        raise failure
    return []


def platform_from(lines: list[str]) -> str | None:
    """The console printed on the box, if one of the lines says so."""
    for line in lines:
        if _platform_key(line) in PLATFORMS:
            return PLATFORMS[_platform_key(line)]
    return None


def search_terms(lines: list[str]) -> list[str]:
    """Box text worth searching — the console name is a filter, not a title
    (searching "PS4" would happily return the wrong game)."""
    return [line for line in lines if _platform_key(line) not in PLATFORMS]


def candidates_from(lines: list[str]) -> list[str]:
    """Search terms for one photo, best-first.

    Models order lines by size, not by meaning, and a two-word logo often comes
    back as two lines ("BLADE", "Stellar" for Stellar Blade). So the big lines
    are also offered joined, both ways round — the catalog throws out whichever
    combinations are nonsense, and that's cheap because lookups are cached.
    """
    terms = search_terms(lines)
    joins = [
        f"{first} {second}"
        for index, first in enumerate(terms[:3])
        for second in terms[:3][index + 1 :]
    ]
    joins += [" ".join(reversed(join.split(" ", 1))) for join in joins]
    # Whole phrases before lone words. A single word off a cover is usually a
    # fragment of the logo, and the catalog will happily match it to the wrong
    # game — bare "BLADE" finds a different Blade than "Stellar BLADE" does.
    return dedupe(
        [
            *[term for term in terms if " " in term],
            *joins,
            *[term for term in terms if " " not in term],
        ]
    )


def dedupe(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value.lower() not in seen:
            seen.add(value.lower())
            out.append(value)
    return out


def _clean(lines: list[str]) -> list[str]:
    stripped = [re.sub(r"^[-*#>\s]+|[\s]+$", "", line).strip(" .") for line in lines]
    return dedupe([line for line in stripped if line and not NOISE.match(line)])


def _platform_key(line: str) -> str:
    """Normalise box print for the PLATFORMS lookup: case, spacing and the
    ®/™/. decoration all vary between boxes and between model answers."""
    return re.sub(r"[^a-z0-9|]", "", line.lower())
