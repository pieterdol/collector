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
    ItemType.TV: TmdbProvider,
    ItemType.GAME: IgdbProvider,
}


def get_provider(item_type: ItemType, db: Session) -> MetadataProvider:
    provider = _REGISTRY[item_type](db)
    provider.item_type = item_type
    return provider


def all_providers(db: Session) -> list[MetadataProvider]:
    return [get_provider(item_type, db) for item_type in _REGISTRY]


__all__ = ["MetadataProvider", "MetadataResult", "get_provider", "all_providers"]
