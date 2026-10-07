from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fs_notifications_challenge.application.events import NotificationCreatedEvent
from fs_notifications_challenge.application.outbox import OutboxMessage, OutboxRepository
from fs_notifications_challenge.application.ports import EventPublisher
from fs_notifications_challenge.infrastructure.models import OutboxMessageModel

PENDING, DONE, DEAD, CANCELLED = "PENDING", "DONE", "DEAD", "CANCELLED"
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (10, 60, 300)


def _now() -> datetime:
    return datetime.now(UTC)


class SQLAlchemyOutboxRepository(OutboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    async def enqueue(self, notification_id: int) -> None:
        self._session.add(OutboxMessageModel(notification_id=notification_id))
        await self._session.flush()  # commit happens with the notification, in get_db


    async def fetch_pending(self, limit: int) -> list[OutboxMessage]:
        # Single worker for now. With several workers on Postgres, add
        # .with_for_update(skip_locked=True) so two don't grab the same row.
        result = await self._session.execute(
            select(OutboxMessageModel)
            .where(
                OutboxMessageModel.status == PENDING,
                OutboxMessageModel.next_attempt_at <= _now(),  
            )
            .order_by(OutboxMessageModel.next_attempt_at)
            .limit(limit),
        )
        return [
            OutboxMessage(
                id=r.id, 
                notification_id=r.notification_id, 
                attempts=r.attempts,
                max_attempts=MAX_ATTEMPTS,    
            )
            for r in result.scalars().all()
        ]


    async def mark_done(self, message_id: int) -> None:
        row = await self._get(message_id)
        if row is None:
            return
        row.attempts += 1
        row.status = DONE
        row.processed_at = _now()
        await self._session.flush()


    async def retry_later(self, message_id: int, error: str) -> None:
        row = await self._get(message_id)
        if row is None:
            return
        row.attempts += 1
        row.last_error = error[:500]
        delay = BACKOFF_SECONDS[min(row.attempts - 1, len(BACKOFF_SECONDS) - 1)]
        row.next_attempt_at = _now() + timedelta(seconds=delay)
        await self._session.flush()


    async def dead_letter(self, message_id: int, error: str) -> None:
        row = await self._get(message_id)
        if row is None:
            return
        row.attempts += 1
        row.last_error = error[:500]
        row.status = DEAD
        row.processed_at = _now()
        await self._session.flush()


    async def reschedule(self, notification_id: int) -> None:
        result = await self._session.execute(
            select(OutboxMessageModel).where(
                OutboxMessageModel.notification_id == notification_id,
                OutboxMessageModel.status.in_((PENDING, DEAD)),
            )
        )
        rows = result.scalars().all()
        if not rows:
            await self.enqueue(notification_id)
            return
        for row in rows:
            row.status = PENDING
            row.attempts = 0
            row.last_error = None
            row.next_attempt_at = _now()
            row.processed_at = None
        await self._session.flush()


    async def cancel(self, notification_id: int) -> None:
        result = await self._session.execute(
            select(OutboxMessageModel).where(
                OutboxMessageModel.notification_id == notification_id,
                OutboxMessageModel.status == PENDING,
            ),
        )
        rows = result.scalars().all()
        for row in rows:
            row.status = CANCELLED
            row.last_error = "Notification deleted."
            row.processed_at = _now()
            await self._session.flush()


    async def _get(self, message_id: int) -> OutboxMessageModel:
        # The worker only touches messages that are still PENDING. If it was 
        # CANCELLED (notification deleted) while the worker held it, leave it be:
        # otherwise mark_done/retry_later would overwrite the audit trail
        row = await self._session.get(OutboxMessageModel, message_id)
        return row if row is not None and row.status == PENDING else None


class OutboxEventPublisher(EventPublisher):
    """Implements the EventPublisher port by writing a durable outbox row.
    Shares the request's session, so the outbox row commits atomically with the
    notification.
    """

    def __init__(self, outbox: OutboxRepository) -> None:
        self._outbox = outbox

    async def publish(self, event: NotificationCreatedEvent) -> None:
        await self._outbox.enqueue(event.notification.id)