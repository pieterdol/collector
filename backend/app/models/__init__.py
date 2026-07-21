"""Import all models so Base.metadata knows every table."""

from app.models.activity_event import ActivityEvent
from app.models.item import Item
from app.models.item_season import ItemSeason
from app.models.platform import Platform
from app.models.provider_cache import ProviderCache
from app.models.user import User

__all__ = ["ActivityEvent", "Item", "ItemSeason", "Platform", "ProviderCache", "User"]
