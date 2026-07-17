"""Provider registry: item type → MetadataProvider instance."""

from sqlalchemy.orm import Session

from app.domain.enums import ItemType
from app.providers.base import MetadataProvider, MetadataResult
from app.providers.igdb import IgdbProvider
from app.providers.openlibrary import OpenLibraryProvider
from app.providers.tmdb import TmdbProvider

_REGISTRY: dict[ItemType, type[MetadataProvider]] = {
    ItemType.BOOK: OpenLibraryProvider,
    ItemType.MOVIE: TmdbProvider,
    ItemType.GAME: IgdbProvider,
}


def get_provider(item_type: ItemType, db: Session) -> MetadataProvider:
    return _REGISTRY[item_type](db)


def all_providers(db: Session) -> list[MetadataProvider]:
    return [cls(db) for cls in _REGISTRY.values()]


__all__ = ["MetadataProvider", "MetadataResult", "get_provider", "all_providers"]
