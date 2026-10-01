from abc import ABC, abstractmethod

from fs_notifications_challenge.application.events import NotificationCreatedEvent
from fs_notifications_challenge.domain.delivery import DeliveryAttempt
from fs_notifications_challenge.domain.notification import Notification
from fs_notifications_challenge.domain.user_profile import UserProfile

class NotificationRepository(ABC):
    @abstractmethod
    async def add(self, notification: Notification) -> Notification:
        """Persist a notification (asigns its id). Does not commit; the 
        session lifecycle (get_db) commits once per request."""
        ...


    @abstractmethod
    async def get(self, notification_id: int) -> Notification | None:
        """Load one notification by id, or None"""
        ...


    @abstractmethod
    async def update(self, notification: Notification) -> Notification:
        """Persist changes to an existing notification (status, sent_at, ...)."""
        ...


    @abstractmethod
    async def list_all(self) -> list[Notification]:
        """Return every notification, newest first."""
        ...


class DeliveryAttemptRepository(ABC):
    @abstractmethod
    async def add(self, attempt: DeliveryAttempt) -> DeliveryAttempt:
        ...


class EventPublisher(ABC):
    """Publishing an event. The outbox implementation records it as a durable 
    row in the same transaction as the notification, so a broker or a different 
    transport can replace it without touching the use cases."""
    
    @abstractmethod
    async def publish(self, event: NotificationCreatedEvent) -> None:
        ...


class UserRepository(ABC):
    @abstractmethod
    async def create(self, user_profile: UserProfile) -> UserProfile:
        """Persist a user profile and return it with its id populated."""
        ...