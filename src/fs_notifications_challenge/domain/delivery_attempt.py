from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from fs_notifications_challenge.domain.notification import Channel, Status


@dataclass
class DeliveryAttempt():
    id: int | None = None
    notitification_id: int
    channel: Channel
    status: Status
    attempted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    detail: str
