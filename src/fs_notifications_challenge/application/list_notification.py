from dataclasses import dataclass

from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.domain.notification import Notification



@dataclass
class ListNotifications:
    repository: NotificationRepository

    async def execute(self) -> list[Notification]:
        return await self.repository.list_all()