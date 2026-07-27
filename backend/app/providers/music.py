"""Music lookups: Discogs when it's configured, MusicBrainz otherwise.

One item type, two catalogues — so this is a thin front for both rather
than a fifth entry in the registry. MusicBrainz needs no key, so music
search always works; adding DISCOGS_TOKEN upgrades it to the deeper
pressing data without changing anything the UI does.

Both mappers emit the same metadata keys, and every external_id is
namespaced (`mb:<uuid>`, `discogs:<id>`), so an item stays re-linkable
against the catalogue it was matched in even after the other one appears.
"""

from sqlalchemy.orm import Session

from app.domain.enums import ItemType
from app.providers.base import MetadataProvider, MetadataResult
from app.providers.discogs import DiscogsProvider
from app.providers.musicbrainz import MusicBrainzProvider


class MusicProvider(MetadataProvider):
    item_type = ItemType.MUSIC

    def __init__(self, db: Session):
        super().__init__(db)
        self.discogs = DiscogsProvider(db)
        self.musicbrainz = MusicBrainzProvider(db)

    @property
    def _primary(self) -> MetadataProvider:
        return self.discogs if self.discogs.available else self.musicbrainz

    @property
    def name(self) -> str:
        """The catalogue actually in use — shown on the Settings page."""
        return self._primary.name

    @property
    def available(self) -> bool:
        return True  # MusicBrainz is keyless; music search is never off

    def search(self, query: str) -> list[MetadataResult]:
        return self._primary.search(query)

    def lookup_barcode(self, code: str) -> MetadataResult | None:
        """Both catalogues index sleeve barcodes, so a miss in one is worth
        a second try in the other — it only costs a request on a miss."""
        for provider in (self._primary, self._other):
            result = provider.lookup_barcode(code)
            if result is not None:
                return result
        return None

    def details(self, external_id: str) -> MetadataResult | None:
        if external_id.startswith("discogs:"):
            return self.discogs.details(external_id)
        if external_id.startswith("mb:"):
            return self.musicbrainz.details(external_id)
        return self._primary.details(external_id)

    @property
    def _other(self) -> MetadataProvider:
        return self.musicbrainz if self._primary is self.discogs else self.discogs
