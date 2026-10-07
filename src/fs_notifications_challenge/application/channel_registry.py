from collections.abc import Iterable

from fs_notifications_challenge.application.ports import ChannelSender
from fs_notifications_challenge.domain.notification import Channel, DomainError


class UnsupportedChannelError(DomainError):
    """No strategy registered for this channel (a wiring bug, not bad input.)"""


class ChannelRegistry:
    """Maps a Channel to its sender strategy. The use case asks the registry,
    never `if channel == EMAIL: ...`, so new channels don't touch it."""


    def __init__(self, senders: Iterable[ChannelSender] = ()) -> None:
        self._senders: dict[Channel, ChannelSender] = {}
        for sender in senders:
            self.register(sender)

    
    def register(self, sender: ChannelSender) -> None:
        if sender.channel in self._senders:
            raise ValueError(f"A sender for {sender.channel.value} is already registered.")
        self._senders[sender.channel] = sender


    def get(self, channel: Channel) -> ChannelSender:
        try:
            return self._senders[channel]
        except KeyError:
            raise UnsupportedChannelError(f"No sender registered for channel {channel.value}.") from None

    @property
    def channels(self) -> frozenset[Channel]:
        return frozenset(self._senders)