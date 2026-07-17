import uuid

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Platform(Base):
    """A gaming platform (console/storefront), synced once from IGDB.

    Rows with igdb_id came from the sync; rows without are custom
    (e.g. "PC (Steam)" created by the Steam import).
    """

    __tablename__ = "platforms"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    igdb_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    abbreviation: Mapped[str | None] = mapped_column(Text)
