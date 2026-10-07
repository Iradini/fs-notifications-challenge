from abc import ABC, abstractmethod

from fs_notifications_challenge.application.events import NotificationCreatedEvent
from fs_notifications_challenge.domain.channel import Channel
from fs_notifications_challenge.domain.delivery import DeliveryAttempt, DeliveryResult
from fs_notifications_challenge.domain.notification import Notification
from fs_notifications_challenge.domain.user import User, UserProfile


class NotificationRepository(ABC):
    @abstractmethod
    async def add(self, notification: Notification) -> Notification:
        """Persist a notification (asigns its id). Does NOT commit; the 
        session lifecycle (get_db) commits once per request."""
        ...


    @abstractmethod
    async def get(self, notification_id: int) -> Notification | None:
        """Load one notification by id, or None if it doesn't exists OR was
        soft-deleted (deleted notifications are invisible to every use case)."""
        ...


    @abstractmethod
    async def update(self, notification: Notification) -> Notification:
        """Persist every mutable filed. Raises ConcurrentUpdateError if someone
        else changed the row since it was loaded."""
        ...


    @abstractmethod
    async def list_all(self) -> list[Notification]:
        """Return every non-deleted notification, newest first."""
        ...


class DeliveryAttemptRepository(ABC):
    @abstractmethod
    async def add(self, attempt: DeliveryAttempt) -> DeliveryAttempt:
        ...


class UserRepository(ABC):
    @abstractmethod
    async def add(self, user: User) -> User:
        """Persist a new user (assing its id)."""
        ...


    @abstractmethod
    async def get(self, user_id: int) -> User | None:
        """Load a user by id or None"""
        ...


    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        ...


    @abstractmethod
    async def save_profile(self, profile: UserProfile) -> UserProfile:
        """Create or replace the user's profile (it's 1:1)"""
        ...


class EventPublisher(ABC):
    """Publishing an event. The outbox implementation records it as a durable 
    row in the same transaction as the notification, so a broker or a different 
    transport can replace it without touching the use cases."""
    
    @abstractmethod
    async def publish(self, event: NotificationCreatedEvent) -> None:
        ...


class ChannelSender(ABC):
    """Strategy for one delivery channel. Each implementation owns its
    channel-specific steps (validate, render/format, transmit) and reports the
    outcome as a DeliveryResult. Adding a channel = a new subclass registered
    in the ChannelRegistry; nothing else changes (open/closed)."""

    channel: Channel

    
    @abstractmethod
    async def send(self, notification: Notification) -> DeliveryResult:
        """Must not raise for expected failures. Return
        DeliveryResult.rejected(...) or DeliveryResult.transient(...)."""
        ...