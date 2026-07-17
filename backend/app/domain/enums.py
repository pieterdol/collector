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
    GAME = "game"


class ItemFormat(StrEnum):
    PHYSICAL = "physical"
    DIGITAL = "digital"


class ItemStatus(StrEnum):
    WISHLIST = "wishlist"
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class EventType(StrEnum):
    ITEM_ADDED = "item_added"
    STATUS_CHANGE = "status_change"
    PROGRESS_UPDATE = "progress_update"
    RATING_SET = "rating_set"
    ACQUIRED = "acquired"
    LOAN_OUT = "loan_out"
    LOAN_RETURN = "loan_return"
    ITEM_DELETED = "item_deleted"


def values(enum_cls: type[StrEnum]) -> list[str]:
    return [e.value for e in enum_cls]
