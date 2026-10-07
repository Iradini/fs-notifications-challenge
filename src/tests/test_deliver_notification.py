import asyncio

from fs_notifications_challenge.application.channel_registry import ChannelRegistry
from fs_notifications_challenge.application.deliver_notification import (
    DeliverNotification,
    Outcome,
)
from fs_notifications_challenge.application.ports import (
    ChannelSender,
    DeliveryAttemptRepository,
    NotificationRepository,
)
from fs_notifications_challenge.domain.delivery import AttemptStatus, DeliveryResult
from fs_notifications_challenge.domain.channel import Channel
from fs_notifications_challenge.domain.contact import ContactInfo 
from fs_notifications_challenge.domain.notification import Notification, Status


class InMemoryNotifications(NotificationRepository):
    def __init__(self, *items):
        self.items = {n.id: n for n in items}


    async def add(self, n):
        self.items[n.id] = n
        return n


    async def get(self, notification_id):
        return self.items.get(notification_id)


    async def update(self, n):
        return n


    async def list_all(self):
        return list(self.items.values())


class InMemoryAttempts(DeliveryAttemptRepository):
    def __init__(self):
        self.items = []


    async def add(self, attempt):
        self.items.append(attempt)
        return attempt


class StubSender(ChannelSender):
    channel = Channel.EMAIL

    def __init__(self, result: DeliveryResult):
        self.result = result
        self.calls = 0


    async def send(self, notification):
        self.calls += 1
        return self.result


def setup(result: DeliveryResult):
    n = Notification(user_id=1, title="t", content="c", channel=Channel.EMAIL, recipient=ContactInfo(email="a@b.co"), id=1)
    sender = StubSender(result)
    attempts = InMemoryAttempts()
    use_case = DeliverNotification(InMemoryNotifications(n), attempts, ChannelRegistry([sender]))
    return n, sender, attempts, use_case


def run(coro):
    return asyncio.run(coro)


def test_success_marks_sent_and_records_attempt():
    n, _, attempts, uc = setup(DeliveryResult.ok(provider_message_id="x"))
    assert run(uc.execute(1, final_attempt=False)).outcome is Outcome.SENT
    assert n.status is Status.SENT and n.sent_at is not None
    assert attempts.items[0].status is AttemptStatus.SUCCESS


def test_permanent_failure_marks_failed_wothout_retry():
    n, _, attempts, uc = setup(DeliveryResult.rejected("bad address"))
    assert run(uc.execute(1, final_attempt=False)).outcome is Outcome.REJECTED
    assert n.status is Status.FAILED and n.last_error == "bad address"
    assert attempts.items[0].detail == {
        "error": "bad address", "retryable": False,
        "message": {"title": "t", "content": "c"},
    }


def test_transient_failure_keeps_created_and_asks_for_retry():
    n, _, attempts, uc = setup(DeliveryResult.transient("timeout"))
    assert run(uc.execute(1, final_attempt=False)).outcome is Outcome.RETRY
    assert n.status is Status.CREATED and n.last_error == "timeout"
    assert attempts.items[0].status == AttemptStatus.FAILED  # attempt recorded anyway


def test_transient_failure_on_last_attempt_is_exhausted():
    n, _, _, uc = setup(DeliveryResult.transient("timeout"))
    assert run(uc.execute(1, final_attempt=True)).outcome is Outcome.EXHAUSTED
    assert n.status is Status.FAILED

def test_deleted_after_enqueue_is_skipped():
    _, sender, attempts, uc = setup(DeliveryResult.ok())
    assert run(uc.execute(999, final_attempt=False)).outcome is Outcome.SKIPPED
    assert sender.calls == 0 and attempts.items == []


def test_already_sent_is_skipped_not_resent():
    n, sender, attempts, uc = setup(DeliveryResult.ok())
    n.mark_sent()
    assert run(uc.execute(1, final_attempt=False)).outcome is Outcome.SKIPPED
    assert sender.calls == 0 and attempts.items == []


def test_give_up_marks_failed_and_records_attempt():
    n, _, attempts, uc = setup(DeliveryResult.ok())
    run(uc.give_up(1, "RuntimeError: boom"))
    assert n.status is Status.FAILED
    assert attempts.items[0].detail["reason"] == "dead_lettered"