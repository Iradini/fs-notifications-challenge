from fs_notifications_challenge.application.create_notification import CreateNotification
from fs_notifications_challenge.application.list_notification import ListNotifications
from fs_notifications_challenge.application.send_notification import SendNotification
from fs_notifications_challenge.domain.notification import Channel, Notification, Status
from fs_notifications_challenge.infrastructure.in_memory_repository import InMemoryNotificationRepository


_repository = InMemoryNotificationRepository(
    seed=[
        Notification(id=1, user_id=1, title="First Notification", content="Welcome to the app!", channel=Channel.EMAIL, recipient="test_recipient", status=Status.CREATED),
        Notification(id=2, user_id=3, title="New Follower", content="You have a new follower.", channel=Channel.SMS, recipient="test_recipient", status=Status.CREATED),
        Notification(id=3, user_id=1, title="Report Ready", content="Your report is ready.", channel=Channel.PUSH, recipient="test_recipient", status=Status.CREATED),
    ],
)

def get_create_notification() -> CreateNotification:
    return CreateNotification(repository=_repository) 


def get_list_notifications() -> ListNotifications:
    return ListNotifications(repository=_repository)


def get_send_notification() -> SendNotification:
    return SendNotification(repository=_repository) 