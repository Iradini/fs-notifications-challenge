from dataclasses import dataclass

from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.domain.notification import Notification


@dataclass
class SendNotification:
    repository: NotificationRepository

    async def execute(
            self,
            sender_id: int,
            recipient_id: int,
            title: str,
            message: str,
    ) -> Notification:
        notification = Notification (
            sender_id=sender_id,
            recipient_id=recipient_id,
            title=title,
            message=message,
        )
        return await self.repository.add(notification)