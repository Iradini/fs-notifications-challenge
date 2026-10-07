from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class OutboxMessage:
    """A pending delivery, as the worker sees it. A plain data object so the
    application layer never touches the ORM row."""

    id: int
    notification_id: int
    attempts: int
    max_attempts: int

    @property
    def is_final_attempt(self) -> bool:
        """True if this processing run is the last one before dead-lettering"""
        return self.attempts + 1 >= self.max_attempts


class OutboxRepository(ABC):
    @abstractmethod
    async def enqueue(self, notification_id: int) -> None:
        """Record that a notification needs delivering. Called in the same
        transaction as creating the notification."""
        ...


    @abstractmethod
    async def fetch_pending(self, limit: int) -> list[OutboxMessage]:
        """Return up to `limit` messages still waiting to be delivered."""
        ...


    @abstractmethod
    async def mark_done(self, message_id: int) -> None:
        ...


    @abstractmethod
    async def retry_later(self, message_id: int, error: str) -> None:
        """Count the attempt and schedule the next one with backoff."""
        ...


    @abstractmethod
    async def dead_letter(self, message_id: int, error: str) -> None:
        """Give up: park the message as DEAD so it can be inspected/replayed."""
        ...


    @abstractmethod
    async def reschedule(self, notification_id: int) -> None:
        """The notification's channel/recipient changed: make its message due
        now with a fresh retry budget (re-enqueue if somehow missing)."""
        ...


    @abstractmethod
    async def cancel(self, notification_id: int) -> None:
        """The notification was deleted: stop any pending delivery. The row is 
        kept (CANCELLED) for the audit trail."""
        ...
