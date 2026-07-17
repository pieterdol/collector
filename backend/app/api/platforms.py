from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.platforms import ensure_platforms_synced
from app.core.security import get_current_user
from app.db import get_db
from app.models import Platform, User

router = APIRouter(prefix="/api/platforms", tags=["platforms"])


@router.get("")
def list_platforms(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """The full platform catalog (for the add-item form).

    Synced from IGDB on first use when Twitch credentials are configured;
    custom platforms (e.g. "PC (Steam)") are always included.
    """
    ensure_platforms_synced(db)
    rows = db.scalars(select(Platform).order_by(Platform.name)).all()
    return {
        "platforms": [
            {"id": str(p.id), "name": p.name, "abbreviation": p.abbreviation}
            for p in rows
        ]
    }
