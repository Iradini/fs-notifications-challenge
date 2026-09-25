from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

class DomainError(Exception):
    """Raised when a business rule is violated"""

@dataclass
class Notification():
    sender_id: int
    recipient_id: int
    title: str
    message: str
    id: int | None = None
    is_read: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None :
        if self.sender_id == self.recipient_id:
            raise DomainError("A user cannot notify themselves.")
        if not self.message.strip():
            raise DomainError("Notification message can't be blank.")