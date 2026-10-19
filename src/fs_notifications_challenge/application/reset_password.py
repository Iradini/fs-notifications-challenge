from dataclasses import dataclass

from fs_notifications_challenge.application.ports import (
    PasswordHasher,
    PasswordResetTokenRepository,
    ResetTokenService,
    UserRepository,
)
from fs_notifications_challenge.domain.errors import DomainError

# One message for every way a link can be bad (unknown, expired, already used,
# its user is gone): telling them apart would help someone guessing links
INVALID_LINK = "This password reset link is invalid or has expired. Please request" \
" a new one."


@dataclass
class ResetPassword:
    users: UserRepository
    tokens: PasswordResetTokenRepository
    secrets: ResetTokenService
    hasher: PasswordHasher


    async def execute(self, token: str, new_password: str) -> None:
        record = await self.tokens.get_by_hash(self.secrets.digest(token))
        if record is None or record.is_expired():
            raise DomainError(INVALID_LINK)
        user = await self.users.get(record.user_id)
        if user is None:
            raise DomainError(INVALID_LINK)

        user.change_password(self.hasher.hash_password(new_password))
        await self.users.update(user)
        await self.tokens.delete_for_user(user.id)      # single use: this link, and any other, is spent