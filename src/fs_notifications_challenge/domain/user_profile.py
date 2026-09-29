from __future__ import annotations

from dataclasses import dataclass

from fs_notifications_challenge.domain.user import User


@dataclass
class UserProfile(User):
    phone: str | None = None
    