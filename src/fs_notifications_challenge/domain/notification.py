from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class Channel(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"


class DomainError(Exception):
    """Raised when a business rule is violated"""


class Status(str, Enum):
    CREATED ="CREATED"
    SENT = "SENT"
    FAILED = "FAILED"


@dataclass
class Notification():
    user_id: int
    title: str
    content: str
    channel: Channel
    recipient: str
    id: int | None = None
    status: Status = Status.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    sent_at: datetime | None = None
    last_error: str | None = None

    def __post_init__(self) -> None :
        if not self.title.strip():
            raise DomainError("Notification title cannot be blank.")
        if not self.content.strip():
            raise DomainError("Notification message cannot be blank.")
        if not self.recipient.strip():
            raise DomainError("Notification recipient cannot be blank.")