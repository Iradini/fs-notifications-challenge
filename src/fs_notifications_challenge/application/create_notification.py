from dataclasses import dataclass

from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.domain.notification import Channel, Notification


@dataclass
class CreateNotification:
    repository: NotificationRepository

    async def execute(
            self,
            id: int,
            user_id: int,
            title: str,
            content: str,
            channel: Channel,
            recipient: str,
    ) -> Notification:
        notification = Notification(
            id=id,
            user_id=user_id,
            title=title,
            content=content,
            channel=channel,
            recipient=recipient,
        )
        return await self.repository.add(notification)