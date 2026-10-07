from fs_notifications_challenge.application.channel_registry import ChannelRegistry
from fs_notifications_challenge.infrastructure.channels.email import EmailSender
from fs_notifications_challenge.infrastructure.channels.provider import SimulatedProvider
from fs_notifications_challenge.infrastructure.channels.push import PushSender
from fs_notifications_challenge.infrastructure.channels.sms import SmsSender


def build_channel_registry(failure_rate: float = 0.0) -> ChannelRegistry:
    """Composition of the channel strategies. A new channel = a new sender
    class + one line here."""
    return ChannelRegistry(
        [
            EmailSender(SimulatedProvider("email", failure_rate)),
            SmsSender(SimulatedProvider("sms", failure_rate)),
            PushSender(SimulatedProvider("push", failure_rate)),
        ],
    )