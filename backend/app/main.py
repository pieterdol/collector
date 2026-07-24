"""FastAPI application entrypoint.

All API routes live under /api; cover images are served from /media.
Both paths are proxied by the frontend nginx, so the browser sees one origin.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import auth, enrich, epic, gog, items, platforms, psn, seasons, stats, steam
from app.config import get_settings

app = FastAPI(title="Collector API", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.include_router(auth.router)
app.include_router(items.router)
app.include_router(seasons.router)
app.include_router(enrich.router)
app.include_router(steam.router)
app.include_router(epic.router)
app.include_router(gog.router)
app.include_router(psn.router)
app.include_router(stats.router)
app.include_router(platforms.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _mount_media(application: FastAPI) -> None:
    media_dir = Path(get_settings().media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    application.mount("/media", StaticFiles(directory=media_dir), name="media")


_mount_media(app)
