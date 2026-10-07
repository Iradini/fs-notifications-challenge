import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from fs_notifications_challenge.application.channel_registry import ChannelRegistry
from fs_notifications_challenge.application.deliver_notification import (
    DeliverNotification,
    Outcome,    
)
from fs_notifications_challenge.infrastructure.outbox import OutboxMessage, OutboxRepository
from fs_notifications_challenge.infrastructure.channels import build_channel_registry
from fs_notifications_challenge.infrastructure.database import AsyncSessionLocal
from fs_notifications_challenge.infrastructure.delivery_repository import SQLAlchemyDeliveryAttemptRepository
from fs_notifications_challenge.infrastructure.outbox import SQLAlchemyOutboxRepository
from fs_notifications_challenge.infrastructure.repository import SQLAlchemyNotificationRepository


logger = logging.getLogger("notifications.worker")

async def _process_message(
        session: AsyncSession,
        outbox: OutboxRepository,
        deliver: DeliverNotification,
        message: OutboxMessage,
) -> None:
    """One message, one commit. Two failure kinds are handled differently:
    - Delivery failed (strategy returned a failed DeliveryResult): a business 
    result. The FAILED attempt + notification status are COMMTED.
    - Code crashed (exception): roll back whatever are happened, then count 
    the attempt on the outbox row; on the last one, dead-letter it and mark 
    the notification FAILED so it doesn't sit in CREATED forever.
    """
    try:
        result = await deliver.execute(message.notification_id, final_attempt=message.is_final_attempt)
    except Exception as exc:  # noqa: BLE001 - the worker must survive one bad message
        await session.rollback()
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("Outbox message %s crashed (attempt %s)", message.id, message.attempts + 1)
        if message.is_final_attempt:
            # Mark the notification FAILED first; if even that crashes, roll it
            # back and still dead-letter the message (no savepoints: SQLite).
            try:
                await deliver.give_up(message.notification_id, error)
            except Exception:  # noqa: BLE001
                await session.rollback()
                logger.exception("Could not mark notification %s as failed", message.notification_id)
            await outbox.dead_letter(message.id, error)
        else:
            await outbox.retry_later(message.id, error)
        await session.commit()
        return

    match result.outcome:
        case Outcome.SENT | Outcome.REJECTED | Outcome.SKIPPED:
            await outbox.mark_done(message.id)
        case Outcome.RETRY:
            await outbox.retry_later(message.id, result.error or "")
        case Outcome.EXHAUSTED:
            await outbox.dead_letter(message.id, result.error or "")
    await session.commit()
    logger.info("Outbox message %s -> %s", message.id, result.outcome.value)


async def _process_one_cycle(registry: ChannelRegistry, poll_limit: int) -> None:
    # The worker runs outside any request, so it owns its own session and commit
    # itself (one commit per message, so each delivery is atomic on its own.)
    async with AsyncSessionLocal() as session:
        outbox = SQLAlchemyOutboxRepository(session)
        deliver = DeliverNotification(
            notifications=SQLAlchemyNotificationRepository(session),
            attempts=SQLAlchemyDeliveryAttemptRepository(session),
            registry=registry,
        )
        pending = await outbox.fetch_pending(limit=poll_limit)
        for message in pending:
            await _process_message(session, outbox, deliver, message)


async def run_outbox_worker(
        poll_interval: float = 2.0, 
        poll_limit: int = 10,
        registry: ChannelRegistry | None = None
) -> None:
    """Poll the outbox forever. Started as a background task in the app lifespan."""
    registry = registry or build_channel_registry()
    logger.info(
        "Outbox worker started (every %.1fs, channels: %s).", 
        poll_interval,
        ", ". join(sorted(c.value for c in registry.channels)),
    )
    while True:
        try:
            await _process_one_cycle(registry, poll_limit)
        except asyncio.CancelledError:
            logger.info("Outbox worker stopping.")
            raise
        except Exception:  # noqa: BLE001 - keep the loop alive across unexpected errors
            logger.exception("Outbox worker crashed; continuing.")
        await asyncio.sleep(poll_interval)