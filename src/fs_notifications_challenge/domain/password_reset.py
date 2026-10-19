from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from fs_notifications_challenge.domain.errors import DomainError


@dataclass
class PasswordResetToken:
    """Permission, for a limited time, to choose a new password.
    
    Only the HASH of the secret is kept. The secret itself lives in the email and
    nowhere else, so a leaked database cannot be turned into account takeovers."""

    user_id: int
    token_hash: str
    expires_at: datetime
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.token_hash.strip():
            raise DomainError("A reset token needs a hash.")


    @classmethod
    def issue(cls, user_id: int, token_hash: str, ttl: timedelta) -> PasswordResetToken:
        return cls(user_id=user_id, token_hash=token_hash, expires_at=datetime.now(UTC) + ttl)


    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)) >= self.expires_at