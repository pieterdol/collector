"""MetadataProvider — the one interface every metadata source implements.

To add a provider: subclass, implement `search` (and optionally
`lookup_barcode` / `details`), then register it in providers/__init__.py.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.domain.enums import ItemType


@dataclass
class MetadataResult:
    """One candidate match from an external catalog."""

    title: str
    item_type: ItemType
    metadata: dict = field(default_factory=dict)
    cover_url: str | None = None
    external_id: str | None = None  # provider-specific id, for details()

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "type": self.item_type.value,
            "metadata": self.metadata,
            "cover_url": self.cover_url,
            "external_id": self.external_id,
        }


class MetadataProvider(ABC):
    name: str
    item_type: ItemType

    def __init__(self, db: Session):
        self.db = db

    @property
    def available(self) -> bool:
        """False when required API keys are missing — UI falls back to manual entry."""
        return True

    @abstractmethod
    def search(self, query: str) -> list[MetadataResult]: ...

    def lookup_barcode(self, code: str) -> MetadataResult | None:
        """Barcode → match. Only meaningful for ISBNs today."""
        return None

    def details(self, external_id: str) -> MetadataResult | None:
        """Optional richer lookup once the user picks a search result."""
        return None
