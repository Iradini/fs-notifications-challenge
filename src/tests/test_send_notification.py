import pytest

from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.application.send_notification import SendNotification
from fs_notifications_challenge.domain.notification import DomainError, Notification


class FakeNotificationRepository(NotificationRepository):
    def __init__(self) -> None:
        self.saved: list[Notification] = []
        self._next_id = 1

    async def add(self, notification: Notification) -> Notification:
        notification.id = self._next_id
        self._next_id += 1
        self.saved.append(notification)
        return notification

    async def list_all(self):
        return await super().list_all()

# @pytest.mark.anyio
async def test_send_notification_persists_and_returns_it():
    repo = FakeNotificationRepository()
    use_case = SendNotification(repository=repo)

    result = await use_case.execute(sender_id=1, recipient_id=2, title="Test", message="Hello")

    assert result.id == 1
    assert len(repo.saved) == 1
    assert repo.saved[0].message == "Hello"

# @pytest.mark.anyio
async def test_cannot_notify_yourself():
    repo = FakeNotificationRepository()
    use_case = SendNotification(repository=repo)

    with pytest.raises(DomainError):
        await use_case.execute(sender_id=1, recipient_id=1, title="Test Error", message="Hi")

    assert repo.saved == []