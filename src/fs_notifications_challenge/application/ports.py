from abc import ABC, abstractmethod

from fs_notifications_challenge.application.events import NotificationCreatedEvent
from fs_notifications_challenge.domain.notification import Notification
from fs_notifications_challenge.domain.user_profile import UserProfile

class NotificationRepository(ABC):
    @abstractmethod
    async def add(self, notification: Notification) -> Notification:
        """Persist a notification and return it with its id populated."""
        ...


    @abstractmethod
    async def list_all(self) -> list[Notification]:
        """Return every notification, newest first."""
        ...


class EventPublisher(ABC):
    """Port for publishing domain events.
    
    The in-process implementation lives in infrastructure. Swapping it for a 
    message broker or an outbox later is a change to that one adapter, not to
    the use case that depend on this interface 
    """


class UserRepository(ABC):
    @abstractmethod
    async def create(self, user_profile: UserProfile) -> UserProfile:
        """Persist a user profile and return it with its id populated."""
        ...