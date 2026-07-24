"""GOG library import — mechanics in core/library_import.py."""

from app.api.store_import import build_store_router
from app.core.library_import import StoreSpec

GOG = StoreSpec(
    runner="gog",
    id_key="gog_product_id",
    storefront="GOG",
    event_source="gog_import",
    file_hint="Heroic's store_cache/gog_library.json",
)

router = build_store_router("/api/gog", "gog", GOG)
