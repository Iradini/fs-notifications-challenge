from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fs_notifications_challenge.application.events import NotificationCreatedEvent
from fs_notifications_challenge.application.outbox import OutboxMessage, OutboxRepository
from fs_notifications_challenge.application.ports import EventPublisher
from fs_notifications_challenge.infrastructure.models import OutboxMessageModel

MAX_ATTEMPTS = 3


class SQLAlchemyOutboxRepository(OutboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    async def enqueue(self, notification_id: int) -> None:
        self._session.add(OutboxMessageModel(notification_id=notification_id))
        await self._session.flush()  # commit happens with the notification, in get_db


    async def fetch_pending(self, limit: int) -> list[OutboxMessage]:
        result = await self._session.execute(
            select(OutboxMessageModel)
            .where(OutboxMessageModel.status == "PENDING")
            .order_by(OutboxMessageModel.created_at)
            .limit(limit),
        )
        return [
            OutboxMessage(id=r.id, notification_id=r.notification_id, attempts=r.attempts)
            for r in result.scalars().all()
        ]


    async def mark_done(self, message_id: int) -> None:
        row = await self._session.get(OutboxMessageModel, message_id)
        if row is None:
            return
        row.status = "DONE"
        row.processed_at = datetime.now(UTC)
        await self._session.flush()


    async def mark_failed(self, message_id: int, error: str) -> None:
        row = await self._session.get(OutboxMessageModel, message_id)
        if row is None:
            return
        row.attempts += 1
        row.last_error = error
        if row.attempts >= MAX_ATTEMPTS:
            row.status = "FAILED"          # give up
            row.processed_at = datetime.now(UTC)
        # else: stay PENDING and gets retried on the next worker cycle
        await self._session.flush()


class OutboxEventPublisher(EventPublisher):
    """Implements the EventPublisher port by writing a durable outbox row.
    Shares the request's session, so the outbox row commits atomically with the
    notification.
    """

    def __init__(self, outbox: OutboxRepository) -> None:
        self._outbox = outbox

    async def publish(self, event: NotificationCreatedEvent) -> None:
        await self._outbox.enqueue(event.notification.id)
