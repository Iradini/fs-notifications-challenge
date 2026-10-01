from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from fs_notifications_challenge.domain.notification import Channel


class AttemptStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass
class DeliveryAttempt():
    """One record of trying to deliver a notification. Created on every attempt, 
    success or failure; the notification keeps the current status, this table
    keeps the history. 
    """
    
    notification_id: int
    channel: Channel
    status: AttemptStatus
    detail: dict[str, Any] | None = None
    id: int | None = None
    attempted_at: datetime = field(default_factory=lambda: datetime.now(UTC))