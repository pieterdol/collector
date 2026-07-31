"""Single source of truth for enum-like values.

Stored as TEXT + CHECK constraints in Postgres (native enums are painful to
change); the frontend mirrors these as TS union types in src/lib/types.ts.
When adding a value: update here, add an Alembic migration that replaces the
CHECK constraint, and update the frontend union.
"""

from enum import StrEnum


class ItemType(StrEnum):
    BOOK = "book"
    MOVIE = "movie"
    TV = "tv"
    GAME = "game"
    MUSIC = "music"


class ItemFormat(StrEnum):
    PHYSICAL = "physical"
    DIGITAL = "digital"


class ItemStatus(StrEnum):
    WISHLIST = "wishlist"
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SeasonOwnership(StrEnum):
    """Per-season ownership for TV; NULL on the row = not tracked yet."""

    OWNED = "owned"
    WISHLIST = "wishlist"


class DiscMedia(StrEnum):
    """Disc media of a physical movie or TV season; mirrors MOVIE_MEDIA in types.ts."""

    DVD = "DVD"
    BLU_RAY = "Blu-ray"
    UHD_BLU_RAY = "Ultra HD Blu-ray"
    VHS = "VHS"


class MusicMedia(StrEnum):
    """Carrier a physical release came on; mirrors MUSIC_MEDIA in types.ts.

    Vinyl sizes stay separate because that is the distinction a record
    collector actually files by (an LP and a 7" single are not the same
    shelf). Providers report free-form format strings — normalize with
    `providers/formats.py` before storing.
    """

    VINYL_LP = "Vinyl LP"
    VINYL_12 = 'Vinyl 12"'
    VINYL_10 = 'Vinyl 10"'
    VINYL_7 = 'Vinyl 7"'
    CD = "CD"
    CASSETTE = "Cassette"


class EventType(StrEnum):
    ITEM_ADDED = "item_added"
    STATUS_CHANGE = "status_change"
    PROGRESS_UPDATE = "progress_update"
    RATING_SET = "rating_set"
    ACQUIRED = "acquired"
    LOAN_OUT = "loan_out"
    LOAN_RETURN = "loan_return"
    ITEM_DELETED = "item_deleted"
    BUNDLED = "bundled"
    UNBUNDLED = "unbundled"
    #: Which copy of a bundle the library shows changed.
    BUNDLE_FRONT = "bundle_front"
    SEASON_ACQUIRED = "season_acquired"
    SEASON_WATCHED = "season_watched"
    SEASON_UPDATED = "season_updated"
    SEASON_REMOVED = "season_removed"
    EPISODE_WATCHED = "episode_watched"


def values(enum_cls: type[StrEnum]) -> list[str]:
    return [e.value for e in enum_cls]
