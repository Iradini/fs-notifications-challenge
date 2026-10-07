from __future__ import annotations

from dataclasses import dataclass
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.errors import DomainError


@dataclass
class UserProfile():
    """A user's own contact details (1:1 with User)."""
    user_id: int
    contact: ContactInfo


    def __post_init__(self) -> None:
        if self.contact.is_empty:
            raise DomainError("A profile requires at least one email, one phone, and one token.")


@dataclass
class User():
    """Identity. HAS a profile"""

    email: str
    id: int | None = None
    profile: UserProfile | None = None


    def __post_init__(self) -> None:
        if not self.email.strip():
            raise DomainError("User email cannot be blank.")