import logging

from fs_notifications_challenge.application.events import NotificationCreatedEvent

logger = logging.getLogger("notifications")


async def log_notification_created(event: NotificationCreatedEvent):
    n = event.notification
    message = (
        f"[listener] NotificationCreatedEvent id={n.id} "
        f"channel={n.channel.value} recipient{n.recipient} status={n.status.value}" 
    )
    logger.info(message)
    print(message) 