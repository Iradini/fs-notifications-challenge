from dataclasses import dataclass

from fs_notifications_challenge.application.outbox import OutboxRepository
from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.domain.channel import Channel
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.errors import NotFoundError
from fs_notifications_challenge.domain.notification import Notification


@dataclass
class UpdateNotification:
    """Title/content: any status(what the notifications panel shows).
    Channel/recipient: only while CREATED, i.e. before the worker picks it up or
    while a delivery waits to retry. The entity enforces both (-> 409)."""

    repository: NotificationRepository
    outbox: OutboxRepository

    async def execute(
            self,
            notification_id: int,
            *,
            title: str | None = None,
            content: str | None = None,
            channel: Channel | None = None,
            recipient: ContactInfo | None = None,
    ) -> Notification:
        notification = await self.repository.get(notification_id)
        if notification is None:
            raise NotFoundError(f"Notification {notification_id} not found.")
        
        # Delivery first: it's refused (409), nothing has been mutated yet.
        delivery_changed = channel is not None or recipient is not None
        if delivery_changed:
            notification.change_delivery(channel=channel, recipient=recipient)

        if title is not None or content is not None:
            notification.edit(title=title, content=content)

        saved = await self.repository.update(notification)  # ConcurrentUpdateError -> 409

        if delivery_changed:
            # New address/channel = a fresh delivery: due now, full retry budget,
            # not the tail end of a 5-minute backoff. Same transaction as the update.
            await self.outbox.reschedule(notification.id)
        return saved