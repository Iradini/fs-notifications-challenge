from dataclasses import dataclass
from enum import Enum

from fs_notifications_challenge.application.channel_registry import ChannelRegistry
from fs_notifications_challenge.application.ports import (
    DeliveryAttemptRepository,
    NotificationRepository,
)
from fs_notifications_challenge.domain.delivery import (
    AttemptStatus, 
    DeliveryAttempt,
    DeliveryResult,    
)
from fs_notifications_challenge.domain.errors import NotFoundError
from fs_notifications_challenge.domain.notification import Notification, Status


class Outcome(str, Enum):
    SENT = "SENT"             # delivered                      -> outbox DONE
    REJECTED = "REJECTED"     # permanent failure              -> outbox DONE
    RETRY = "RETRY"           # transient, attempts left       -> outbox retry_later
    EXHAUSTED = "EXHAUSTED"   # transient, no attempts left    -> outbox dead_letter
    SKIPPED = "SKIPPED"       # already processed (idempotent) -> outbox DONE


@dataclass(frozen=True)
class DeliveryOutcome:
    outcome: Outcome
    error: str | None = None


@dataclass
class DeliverNotification:
    """The 'listener' work, driven by the outbox worker: pick the strategy for
    the notification's channel, run it, then record the result on the 
    notification AND as DeliveryAttempt (always - success or failure).

    Returns an outcome instead of raising, so the worker can tell "delivery
    failed" (a business result, committed) from "the code crashed" (rolled back).
    """

    notifications: NotificationRepository
    attempts: DeliveryAttemptRepository
    registry: ChannelRegistry

    async def execute(self, notification_id: int, *, final_attempt: bool) -> DeliveryOutcome:
        notification = await self.notifications.get(notification_id)

        # Deleted (soft) after it was enqueued: nothing left to deliver
        if notification is None:
            return DeliveryOutcome(Outcome.SKIPPED)
        
        # Outbox delivery is at-least-once: if this message is ever processed
        # twice, don't send twice.
        if notification.status is not Status.CREATED:
            return DeliveryOutcome(Outcome.SKIPPED)

        sender = self.registry.get(notification.channel)
        result = await sender.send(notification)

        if result.success:
            notification.mark_sent()
            outcome = DeliveryOutcome(Outcome.SENT)
        elif not result.retryable:
            notification.mark_failed(result.error or "Delivery rejected.")
            outcome = DeliveryOutcome(Outcome.REJECTED, result.error)
        elif final_attempt:
            notification.mark_failed(f"Gave up after retries: {result.error}")
            outcome = DeliveryOutcome(Outcome.EXHAUSTED, result.error)
        else:
            notification.record_error(result.error or "Transient delivery error.")
            outcome = DeliveryOutcome(Outcome.RETRY, result.error)

        await self.notifications.update(notification)
        await self.attempts.add(self._attempt_from(notification, result))
        return outcome


    async def give_up(self, notification_id: int, error: str) -> None:
        """Called by the worker when a message is dead-lettered after unexpected
        errors (exceptions, not DeliveryResults), so the notification doesn't 
        sit in CREATED forever and the failure still leaves a DeliveryAttempt. """
        notification = await self._load(notification_id)
        if notification.status is not Status.CREATED:
            return
        notification.mark_failed(error)
        await self.notifications.update(notification)
        await self.attempts.add(
            DeliveryAttempt(
                notification_id=notification.id,
                channel=notification.channel,
                status=AttemptStatus.FAILED,
                detail={"error": error, "reason": "dead_lettered"},
            ),
        )


    async def _load(self, notification_id: int) -> Notification:
        notification = await self.notifications.get(notification_id)
        if notification is None:
            raise NotFoundError(f"Notification {notification_id} not found.")
        return notification


    @staticmethod
    def _attempt_from(notification: Notification, result: DeliveryResult) -> DeliveryAttempt:
        detail = dict(result.detail)
        # Snapshot of the text as it went out. Title/content can be edited after
        # SENT, so this is the only record of what the recipient actually got.
        detail["message"] = {"title": notification.title, "content": notification.content}
        if not result.success:
            detail["error"] = result.error
            detail["retryable"] = result.retryable
        return DeliveryAttempt(
            notification_id=notification.id,
            channel=notification.channel,
            status=AttemptStatus.SUCCESS if result.success else AttemptStatus.FAILED,
            detail=detail,
        )