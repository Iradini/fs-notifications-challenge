import re

from jinja2 import Environment, select_autoescape

from fs_notifications_challenge.application.ports import ChannelSender
from fs_notifications_challenge.domain.delivery import DeliveryResult
from fs_notifications_challenge.domain.notification import Channel, Notification
from fs_notifications_challenge.infrastructure.channels.provider import (
    ProviderUnavailableError,
    SimulatedProvider,
)

# Deliberately loose: real validation is "send and see if it bounces."
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

TEMPLATE_NAME = "notification_email_v1"
_TEMPLATE ="""<!doctype html>
<html>
  <body>
    <h1>{{ title }}</h1>
    <p>{{ content }}</p>
    <hr>
    <small>Sent by fs-notifications</small>
  </body>
</html>"""


class EmailSender(ChannelSender):
    """EMAIL: validate address -> render template -> transmit."""

    channel = Channel.EMAIL

    def __init__(self, provider: SimulatedProvider | None = None, from_address: str = "no-reply@mirina.dev") -> None:
        self._provider = provider or SimulatedProvider("email")
        self._from = from_address
        # autoescape: title/content are user input going into HTML.
        self._template = Environment(autoescape=select_autoescape(default=True)).from_string(_TEMPLATE)


    async def send(self, notification: Notification) -> DeliveryResult:
        # Formats were validated at the API; re-checked here as a safety net.
        recipient = (notification.recipient.address_for(self.channel) or "").strip()
        if not EMAIL_RE.fullmatch(recipient):
            return DeliveryResult.rejected("Invalid email address.", to=recipient)

        html = self._template.render(title=notification.title, content=notification.content)
        payload = {
            "from": self._from,
            "to": recipient,
            "subject": notification.title,
            "html": html,
            "text": notification.content,
        }
        try:
            message_id = await self._provider.transmit(payload)
        except ProviderUnavailableError as exc:
            return DeliveryResult.transient(str(exc), to=recipient, template=TEMPLATE_NAME)

        return DeliveryResult.ok(
            provider_message_id=message_id,
            to=recipient,
            template=TEMPLATE_NAME,
            subject=notification.title,
            html_length=len(html),
        )