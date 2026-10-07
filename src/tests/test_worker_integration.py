"""End-to-end through the real repositories on an in-memory SQLite DB:
outbox row -> worker -> strategy -> notification status + delivery_attempts."""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from fs_notifications_challenge.application.channel_registry import ChannelRegistry
from fs_notifications_challenge.application.deliver_notification import DeliverNotification
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.channel import Channel
from fs_notifications_challenge.domain.notification import Notification
from fs_notifications_challenge.infrastructure.channels import build_channel_registry
from fs_notifications_challenge.infrastructure.database import Base
from fs_notifications_challenge.infrastructure.delivery_repository import (
    SQLAlchemyDeliveryAttemptRepository,
)
from fs_notifications_challenge.infrastructure.models import (
    DeliveryAttemptModel,
    NotificationModel,
    OutboxMessageModel,
    UserModel,
)
from fs_notifications_challenge.infrastructure.outbox import SQLAlchemyOutboxRepository
from fs_notifications_challenge.infrastructure.repository import SQLAlchemyNotificationRepository
from fs_notifications_challenge.infrastructure.worker import _process_message


async def _scenario(channel: Channel, recipient: str, failure_rate: float, cycles: int, registry=None):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # "POST": notification + outbox row in one transaction
    field = {Channel.EMAIL: "email", Channel.SMS: "phone", Channel.PUSH: "token"}[channel]
    async with Session() as s:
        s.add(UserModel(id=1, email="owner@example.com"))
        n = await SQLAlchemyNotificationRepository(s).add(
            Notification(user_id=1, title="Hi", content="There", channel=channel, 
                         recipient=ContactInfo(**{field: recipient}),
            ),
        )
        await SQLAlchemyOutboxRepository(s).enqueue(n.id)
        await s.commit()

    registry = registry or build_channel_registry(failure_rate=failure_rate)
    for _ in range(cycles):
        async with Session() as s:
            # Skip the backoff wait so the test doesn't sleep.
            for row in (await s.execute(select(OutboxMessageModel))).scalars():
                row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
            await s.commit()

            outbox = SQLAlchemyOutboxRepository(s)
            deliver = DeliverNotification(
                SQLAlchemyNotificationRepository(s), SQLAlchemyDeliveryAttemptRepository(s), registry,
            )
            for message in await outbox.fetch_pending(10):
                await _process_message(s, outbox, deliver, message)

    async with Session() as s:
        notif = await s.get(NotificationModel, n.id)
        msg = (await s.execute(select(OutboxMessageModel))).scalar_one()
        attempts = (await s.execute(select(DeliveryAttemptModel))).scalars().all()
        out = notif.status, msg.status, msg.attempts, [a.status for a in attempts]
    await engine.dispose()
    return out


def test_happy_path_email():
    assert asyncio.run(_scenario(Channel.EMAIL, "ana@example.com", 0.0, cycles=2)) == (
        "SENT", "DONE", 1, ["SUCCESS"],
    )


def test_invalid_recipient_fails_once_no_retry():
    assert asyncio.run(_scenario(Channel.SMS, "099123456", 0.0, cycles=3)) == (
        "FAILED", "DONE", 1, ["FAILED"],
    )


def test_provider_down_retries_then_dead_letters():
    assert asyncio.run(_scenario(Channel.PUSH, "tok_" + "x" * 40, 1.0, cycles=5)) == (
        "FAILED", "DEAD", 3, ["FAILED", "FAILED", "FAILED"],
    )


def test_chash_retries_then_dead_letters_and_marks_failed():
    assert asyncio.run(_scenario(Channel.EMAIL, "ana@example.com", 0.0, cycles=4, registry=ChannelRegistry())) == (
        "FAILED", "DEAD", 3, ["FAILED"],
    )