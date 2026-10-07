import re

from fs_notifications_challenge.application.ports import ChannelSender
from fs_notifications_challenge.domain.delivery import DeliveryResult
from fs_notifications_challenge.domain.notification import Channel, Notification
from fs_notifications_challenge.infrastructure.channels.provider import (
    ProviderUnavailableError,
    SimulatedProvider,
)

# E.164: "+" then country code and number, max 15 digits. e.g. +59899123456
E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")

# One SMS segment is 160 chars in GSM-7, but only 70 in UCS-2. Any character
# outside GSM-7 (á, í, ó, ú, emoji...) switches the WHOLE message to UCS-2.
GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà",
) 
GSM7_EXTENDED = set("^{}\\[~]|€\f")  # cost 2 units each (escape + char)
GSM7_LIMIT = 160
UCS2_LIMIT = 70
ELLIPSIS = "..."


def _is_gsm7(text: str) -> bool:
    return all(c in GSM7_BASIC or c in GSM7_EXTENDED for c in text)


def _units(char: str, gsm7: bool) -> int:
    if gsm7:
        return 2 if char in GSM7_EXTENDED else 1
    return len(char.encode("utf-16-le")) // 2  # emoji = 2 UCS-2 units


def fit_single_segment(text: str) -> tuple[str, str, bool]:
    """Return (text, encoding, truncated) so the message fits the one segment."""
    gsm7 = _is_gsm7(text)
    limit = GSM7_LIMIT if gsm7 else UCS2_LIMIT
    encoding = "GSM-7" if gsm7 else "UCS-2"

    if sum(_units(c, gsm7) for c in text) <= limit:
        return text, encoding, False

    budget = limit - len(ELLIPSIS)
    kept: list[str] = []
    used = 0
    for char in text:
        cost = _units(char, gsm7)
        if used + cost > budget:
            break
        kept.append(char)
        used += cost
    return "".join(kept).rstrip() + ELLIPSIS, encoding, True


class SmsSender(ChannelSender):
    """SMS: validate number -> compose + fit to one segment -> transmit."""

    channel = Channel.SMS

    def __init__(self, provider: SimulatedProvider | None = None) -> None:
        self._provider = provider or SimulatedProvider("sms")


    async def send(self, notification: Notification) -> DeliveryResult:
        raw_number = notification.recipient.address_for(self.channel) or ""
        number = re.sub(r"[\s\-()]", "", raw_number)  # tolerate "+598 99 123 456"
        if not E164_RE.fullmatch(number):
            return DeliveryResult.rejected(
                "Invalid phone number: expected E.164, e.g. +59899123456.",
                to=raw_number,
            )

        raw = " ".join(f"{notification.title}: {notification.content}".split())
        text, encoding, truncated = fit_single_segment(raw)

        try:
            message_id = await self._provider.transmit({"to": number, "body": text})
        except ProviderUnavailableError as exc:
            return DeliveryResult.transient(str(exc), to=number)

        return DeliveryResult.ok(
            provider_message_id=message_id,
            to=number,
            text=text,
            encoding=encoding,
            truncated=truncated,
            original_length=len(raw),
        )