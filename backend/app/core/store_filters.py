"""Telling real games apart from the rest of a storefront library.

Every store sells more than games — companion apps, demos, playtests,
soundtracks, media apps, launcher redistributables — and none of them
flag it reliably. These heuristics feed the import review step, which
shows every exclusion with its reason so a false positive is one click
from being rescued.
"""

import re

# Words that only mean "junk" in the right shape: "Alpha Protocol" and
# "Quest of the Avatar" are games, "Concord Alpha" and "Avatar Pack" aren't.
# Anchored to the end of the title, or followed by a pack/kit-ish noun.
_TRAILING = (
    r"(?:demo|beta|alpha|playtest|closed test|open test|network test|technical test"
    # extras that read as junk even at the end of a title — but not
    # "avatar", which ends real games ("Quest of the Avatar")
    r"|soundtrack|art ?book|wallpaper)"
)
_QUALIFIED = r"(?:avatar|theme|soundtrack|art ?book|wallpaper)"

_EXTRA_PATTERN = re.compile(
    # unambiguous on its own
    r"\b(playtest|character creator|dynamic theme|benchmark|companion app|"
    r"media player|redistributables?|dedicated server|"
    # trailing "… Demo" / "… (Beta)" / "… Alpha" / "… Soundtrack", with an
    # optional version number or closing bracket
    rf"{_TRAILING}(?:\s*\d+)?(?:\s*[\)\]])?$|"
    # "Avatar Pack", "Theme Bundle", "Soundtrack DLC"
    rf"{_QUALIFIED}\s+(?:pack|set|bundle|kit|dlc|collection))\b",
    re.IGNORECASE,
)

_MEDIA_APPS = {
    "prime video", "amazon prime video", "netflix", "youtube", "twitch",
    "spotify", "disney+", "crunchyroll", "hulu", "plex", "apple tv",
    "wwe network", "hbo max", "paramount+", "pluto tv", "tubi", "funimation",
    "vlc", "now tv", "videostream",
    # Dutch storefront names.
    "mediaspeler", "nlziet",
}


def name_key(name: str) -> str:
    """Comparable form of a title: no trademark glyphs, case-insensitive."""
    return re.sub(r"[™®]", "", name or "").casefold().strip()


def owned_verdict(
    name: str, platform: str, owned: dict[str, set[str | None]]
) -> tuple[str | None, str | None]:
    """(reason, note) for a title the user may already have.

    Same game, same platform → a duplicate worth excluding. Same game on
    another platform → a candidate with a note: owning a game on PS5
    shouldn't block importing the PC copy, since they're separate copies.
    An existing copy with no platform recorded counts as the same one.
    """
    platforms = owned.get(name_key(name))
    if not platforms:
        return None, None
    if platform in platforms or None in platforms:
        return "already in your collection", None
    others = sorted(p for p in platforms if p)
    return None, f"also owned on {', '.join(others)}"


def classify(name: str, category: str | None = None) -> str | None:
    """Reason this entitlement isn't a game, or None if it looks like one.

    `category` is the store's own type hint when available (PSN's
    played-titles category); anything without "game" in it is an app.
    """
    if name_key(name) in _MEDIA_APPS:
        return "media app"
    if isinstance(category, str) and category and "game" not in category.lower():
        return "app, not a game (store category)"
    match = _EXTRA_PATTERN.search(name or "")
    if match:
        return f'name contains "{match.group(1)}"'
    return None
