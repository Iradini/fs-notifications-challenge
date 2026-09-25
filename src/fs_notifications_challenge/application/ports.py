from abc import ABC, abstractmethod

from fs_notifications_challenge.domain.notification import Notification

class NotificationRepository(ABC):
    @abstractmethod
    async def add(self, notification: Notification) -> Notification:
        """Persist a notification and return it with its id populated."""
        ...


    @abstractmethod
    async def list_all(self) -> list[Notification]:
        """Return every notification, newest first."""
        ...
