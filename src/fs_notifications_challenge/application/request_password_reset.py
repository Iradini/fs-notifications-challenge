from dataclasses import dataclass
from datetime import timedelta


from fs_notifications_challenge.application.ports import (
    PasswordResetMailer,
    PasswordResetTokenRepository,
    ResetTokenService,
    UserRepository,
)
from fs_notifications_challenge.domain.password_reset import PasswordResetToken


@dataclass
class RequestPasswordReset:
    users: UserRepository
    tokens: PasswordResetTokenRepository
    secrets: ResetTokenService
    mailer:PasswordResetMailer
    ttl: timedelta

    async def execute(self, email: str) -> None:
        user = await self.users.get_by_email(email)
        if user is None:
            # Return exactly like the success path: if this raised NotFoundError the
            # form could be used to find out which emails have an account.
            return

        await self.tokens.delete_for_user(user.id)      # one live link per user: the newest
        secret = self.secrets.generate()
        await self.tokens.add(PasswordResetToken.issue(user.id, self.secrets.digest(secret), self.ttl))
        await self.mailer.send_reset_link(user.email, secret)