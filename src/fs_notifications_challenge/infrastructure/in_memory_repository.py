from itertools import count

from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.domain.notification import Notification


class InMemoryNotificationRepository(NotificationRepository):
    """Stores notifications in a plain Python list."""

    def __init__(self, seed: list[Notification] | None = None) -> None:
        self._items: list[Notification] = []
        self._ids = count(1)
        for notification in seed or []:
            notification.id = next(self._ids)
            self._items.append(notification)

    async def add(self, notification: Notification) -> Notification:
        notification.id = next(self._ids)
        self._items.append(notification)
        return notification

    async def list_all(self) -> list[Notification]:
        return list(reversed(self._items)) # Newest first