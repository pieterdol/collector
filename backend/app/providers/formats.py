"""Normalize a provider's free-form format text to one MusicMedia value.

MusicBrainz names the carrier (`12" Vinyl`, `Cassette`), Discogs names it
plus a list of descriptions (`Vinyl` + `LP, Album, 12"`). Both collapse
onto the shelf label a collector files by — see MusicMedia in
domain/enums.py.
"""

import re

from app.domain.enums import MusicMedia

_SIZES = ((r'\b7"|\b7\s*inch', MusicMedia.VINYL_7), (r'\b10"|\b10\s*inch', MusicMedia.VINYL_10),
          (r'\b12"|\b12\s*inch', MusicMedia.VINYL_12))


def music_media(*raw: str | None) -> str | None:
    """Best MusicMedia value for the given format strings, or None.

    None covers carriers the app doesn't shelve (digital media, DVD-Audio)
    as well as missing data — both mean "don't claim a format".
    """
    text = " ".join(part for part in raw if part).lower()
    if not text:
        return None
    if "vinyl" in text or re.search(r"\blp\b", text):
        # "LP" is Discogs' word for an album-length record; it wins over the
        # bare diameter, which on its own signals a single or maxi.
        if re.search(r"\blp\b", text):
            return MusicMedia.VINYL_LP.value
        for pattern, media in _SIZES:
            if re.search(pattern, text):
                return media.value
        return MusicMedia.VINYL_LP.value
    if "cassette" in text or "tape" in text:
        return MusicMedia.CASSETTE.value
    if "cd" in text:  # CD, SACD, HDCD, "Enhanced CD"
        return MusicMedia.CD.value
    return None


def track_length(milliseconds: int | None) -> str | None:
    """250999 → "4:11". Providers that already send "4:11" skip this."""
    if not milliseconds:
        return None
    total = round(milliseconds / 1000)
    return f"{total // 60}:{total % 60:02d}"
