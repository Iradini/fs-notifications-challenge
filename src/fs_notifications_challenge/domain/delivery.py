from __future__ import annotations

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

    `detail` is free-form JSON: on success, what was sent (rendered template,
    truncation info, push payload...); on failure, the error and its context. 
    """
    
    notification_id: int
    channel: Channel
    status: AttemptStatus
    detail: dict[str, Any] | None = None
    id: int | None = None
    attempted_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class DeliveryResult:
    """What a channel strategy reports back. Strategies never persist anything
    and never raise for expected failures. They return one of these and the 
    use case decides what it means for the notification.
    
    - success:           delivered
    - retryable=False:   permanent rejection (bad address, payload too big...).
                         Retrying would just fail the same way.
    - retryable=True:    transient (provider timeout / 5xx). Worth retrying.
    """

    success: bool
    detail: dict[str | Any] = field(default_factory=dict)
    error: str | None = None
    retryable: bool = False

    @classmethod
    def ok(cls, **detail: Any) -> DeliveryResult:
        return cls(success=True, detail=detail)


    @classmethod
    def rejected(cls, error: str, **detail: Any) -> DeliveryResult:
        return cls(success=False, error=error, retryable=False, detail=detail)


    @classmethod
    def transient(cls, error: str, **detail: Any) -> DeliveryResult:
        return cls(success=False, error=error, retryable=True, detail=detail)