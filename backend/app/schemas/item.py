import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import ItemFormat, ItemStatus, ItemType

# Ratings are half-star steps between 0 and 5.
Rating = Annotated[Decimal, Field(ge=0, le=5)]


def _validate_half_steps(value: Decimal | None) -> Decimal | None:
    if value is not None and (value * 2) % 1 != 0:
        raise ValueError("rating must be in half-star steps (0, 0.5, … 5)")
    return value


class ItemCreate(BaseModel):
    type: ItemType
    format: ItemFormat | None = None
    status: ItemStatus = ItemStatus.BACKLOG
    title: str = Field(min_length=1, max_length=500)
    metadata: dict = Field(default_factory=dict)
    cover_url: str | None = None  # remote cover to download once (see core/covers.py)

    progress_current: Decimal | None = None
    progress_total: Decimal | None = None
    rating: Rating | None = None
    review: str | None = None

    purchase_price: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    acquisition_date: date | None = None

    _half_steps = field_validator("rating")(_validate_half_steps)


class ItemUpdate(BaseModel):
    """PATCH body: only provided fields are applied."""

    format: ItemFormat | None = None
    status: ItemStatus | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    metadata: dict | None = None
    cover_url: str | None = None

    progress_current: Decimal | None = None
    progress_total: Decimal | None = None
    rating: Rating | None = None
    review: str | None = None

    purchase_price: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    acquisition_date: date | None = None

    borrowed_by: str | None = None
    loaned_date: date | None = None
    returned_date: date | None = None

    _half_steps = field_validator("rating")(_validate_half_steps)


class AcquireIn(BaseModel):
    format: ItemFormat
    purchase_price: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    acquisition_date: date | None = None
    # Games: the platform you bought it on.
    platform: str | None = Field(default=None, max_length=100)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    format: str | None
    status: str
    title: str
    cover_path: str | None
    metadata: dict = Field(validation_alias="meta")
    # Resolved platform name (games); falls back to legacy metadata.platform.
    platform: str | None = None

    progress_current: Decimal | None
    progress_total: Decimal | None
    rating: Decimal | None
    review: str | None

    purchase_price: Decimal | None
    currency: str | None
    acquisition_date: date | None

    borrowed_by: str | None
    loaned_date: date | None
    returned_date: date | None

    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class ItemListOut(BaseModel):
    items: list[ItemOut]
    total: int


class ActivityEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    old_value: dict | None
    new_value: dict | None
    created_at: datetime


class ActivityListOut(BaseModel):
    events: list[ActivityEventOut]
