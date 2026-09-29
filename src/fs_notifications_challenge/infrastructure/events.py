from collections.abc import Awaitable, Callable

from fs_notifications_challenge.application.events import NotificationCreatedEvent
from fs_notifications_challenge.application.ports import EventPublisher

Handler = Callable[[NotificationCreatedEvent], Awaitable[None]]


class InProcessEventPublisher(EventPublisher):
    """Simplest possible publisher: keeps a list of async handlers and calls
    them in order when an event is published. No broker, no network, no infra.
    
    Because it implements the EventPublisher port, a broker- or outbox-backed
    publisher can replace it later without touching any use case.
    """

    def __init__(self) -> None:
        self._handlers: list[Handler] = []

    def subscribe(self, handler: Handler) -> None:
        self._handlers.append(handler)

    async def  publish(self, event: NotificationCreatedEvent) -> None:
        for handler in self._handlers:
            await handler(event)
