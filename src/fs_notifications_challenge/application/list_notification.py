from dataclasses import dataclass

from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.domain.notification import Notification


@dataclass(frozen=True)
class NotificationPage:
    """One slice of a user's notifications and where it sits in the whole list."""

    items: list[Notification]
    total: int
    skip: int
    limit: int

    @property
    def has_more(self) -> bool:
        return self.skip + len(self.items) < self.total


@dataclass
class ListNotifications:
    """A user only ever sees their own notifications."""

    repository: NotificationRepository

    async def execute(self, user_id: int, skip: int, limit: int) -> NotificationPage:
        items = await self.repository.list_for_user(user_id, skip=skip, limit=limit)
        total = await self.repository.count_for_user(user_id)
        return NotificationPage(items=items, total=total, skip=skip, limit=limit)