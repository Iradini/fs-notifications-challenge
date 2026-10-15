from dataclasses import dataclass

from fs_notifications_challenge.application.ports import PasswordHasher, UserRepository
from fs_notifications_challenge.domain.errors import DomainError, NotFoundError


@dataclass
class ChangePassword:
    """Needs the current password even though the caller is logged in: a stolen
    or left-open session must not be enough to take over the account."""

    repository: UserRepository
    hasher: PasswordHasher

    async def execute(self, user_id: int, current_password: str, new_password: str) -> None:
        user = await self.repository.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        # DomainError (422), not AuthenticationError (401): the page treats a 401 as
        # "your session is over" and sends you to /login, and a typo is not that.
        if not user.password_hash or not self.hasher.verify_password(current_password, user.password_hash):
            raise DomainError("Current password is incorrect.")
        if new_password == current_password:
            raise DomainError("The new password must be different from the current one.")
        user.change_password(self.hasher.hash_password(new_password))
        await self.repository.update(user)