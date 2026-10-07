import json
import re

from fs_notifications_challenge.application.ports import ChannelSender
from fs_notifications_challenge.domain.delivery import DeliveryResult
from fs_notifications_challenge.domain.notification import Channel, Notification
from fs_notifications_challenge.infrastructure.channels.provider import (
    ProviderUnavailableError, 
    SimulatedProvider,    
)


# FCM/APNs tokens are log opaque strings; this rejects obvious garbage.
DEVICE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-:.]{32,4095}$")
TITLE_MAX = 65
BODY_MAX = 240
MAX_PAYLOAD_BYTES = 4095   # FCM / APMs payload limit


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit-1].rstrip() + "…"


def _mask(token: str) -> str:
    return f"{token[:6]}…{token[-4:]}"


class PushSender(ChannelSender):
    """PUSH validate device token -> format payload (+ size check) -> transmit."""
    channel = Channel.PUSH

    def __init__(self, provider: SimulatedProvider | None = None) -> None:
        self._provider = provider or SimulatedProvider("push")


    async def send(self, notification: Notification) -> DeliveryResult:
        token = (notification.recipient.address_for(self.channel) or "").strip()
        if not DEVICE_TOKEN_RE.fullmatch(token):
            return DeliveryResult.rejected("Invalid device token.", token=_mask(token) if len(token) > 10 else "***")

        message = {
            "notification": {
                "title": _clip(notification.title, TITLE_MAX),
                "body": _clip(notification.content, BODY_MAX),
            },
            "data" : {"notification_id": str(notification.id)},
        }
        size = len(json.dumps(message, ensure_ascii=False).encode("utf-8"))
        if size > MAX_PAYLOAD_BYTES:
            return DeliveryResult.rejected(f"Push payload too large ({size} bytes).", payload_bytes=size)

        try:
            message_id = await self._provider.transmit({"token": token, **message})
        except ProviderUnavailableError as exc:
            return DeliveryResult.transient(str(exc), token=_mask(token))

        return DeliveryResult.ok(
            provider_message_id=message_id,
            token=_mask(token),
            payload=message,
            payload_bytes=size,
        ) 