"""Central place where activity events are written.

Every item mutation records its event here, inside the caller's transaction,
so the log can never drift from the actual state change.
"""

import uuid

from sqlalchemy.orm import Session

from app.domain.enums import EventType
from app.models import ActivityEvent


def record_event(
    db: Session,
    *,
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    event_type: EventType,
    old_value: dict | None = None,
    new_value: dict | None = None,
) -> ActivityEvent:
    event = ActivityEvent(
        item_id=item_id,
        user_id=user_id,
        event_type=event_type.value,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(event)
    return event
