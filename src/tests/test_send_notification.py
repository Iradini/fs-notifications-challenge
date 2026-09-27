import pytest

from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.application.create_notification import CreateNotification
from fs_notifications_challenge.domain.notification import DomainError, Channel, Notification, Status


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
async def test_create_notification_persists_and_returns_it():
    repo = FakeNotificationRepository()
    use_case = CreateNotification(repository=repo)

    result = await use_case.execute(
        id=1, user_id=1, title="Test", content="Hello", channel=Channel.EMAIL, recipient="test_recipient",
    )

    assert result.id == 1
    assert len(repo.saved) == 1
    assert repo.saved[0].content == "Hello"

# @pytest.mark.anyio
async def test_recipient_cannot_be_empty():
    repo = FakeNotificationRepository()
    use_case = CreateNotification(repository=repo)

    with pytest.raises(DomainError):
        await use_case.execute(
            id=1, user_id=1, title="Test Error", content="Hi", channel=Channel.EMAIL, recipient="",
        )

    assert repo.saved == []