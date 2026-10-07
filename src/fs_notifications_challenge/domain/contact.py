from dataclasses import dataclass

from fs_notifications_challenge.domain.channel import Channel


@dataclass(frozen=True)
class ContactInfo:
    """Where someone can be reached. A notification's recipient and a user's
    profile both have one."""

    email: str | None = None
    phone: str | None = None
    token: str | None = None


    def address_for(self, channel: Channel) -> str | None:
        return {Channel.EMAIL: self.email, Channel.SMS: self.phone, Channel.PUSH: self.token}[channel]


    @property
    def is_empty(self) -> bool:
        return not (self.email or self.phone or self.token)