"""Epic library import — mechanics in core/library_import.py."""

from app.api.store_import import build_store_router
from app.core.library_import import StoreSpec

EPIC = StoreSpec(
    runner="legendary",
    id_key="epic_app_name",
    storefront="Epic Games Store",
    event_source="epic_import",
    file_hint=(
        "Heroic's store_cache/legendary_library.json or the output of "
        "`legendary list --json`"
    ),
)

router = build_store_router("/api/epic", "epic", EPIC)
