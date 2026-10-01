from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class OutboxMessage:
    """A pending delivery, as the worker sees it. A plain data object so the
    application layer never touches the ORM row."""

    id: int
    notification_id: int
    attempts: int


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
    async def mark_failed(self, message_id: int, error: str) -> None:
        """Record a failed attempt. Keeps the message retryable until it hits
        the max attempts, then marks it permanently failed."""
        ...