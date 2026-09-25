from fs_notifications_challenge.application.list_notification import ListNotifications
from fs_notifications_challenge.application.send_notification import SendNotification
from fs_notifications_challenge.domain.notification import Notification
from fs_notifications_challenge.infrastructure.in_memory_repository import InMemoryNotificationRepository


_repository = InMemoryNotificationRepository(
    seed=[
        Notification(sender_id=1, recipient_id=2, title="First Notification", message="Welcome to the app!"),
        Notification(sender_id=3, recipient_id=2, title="New Follower", message="You have a new follower."),
        Notification(sender_id=1, recipient_id=2, title="Report Ready", message="Your report is ready."),
    ],
)


def get_list_notifications() -> ListNotifications:
    return ListNotifications(repository=_repository)


def get_send_notification() -> SendNotification:
    return SendNotification(repository=_repository) 