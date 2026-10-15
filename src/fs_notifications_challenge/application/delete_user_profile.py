from dataclasses import dataclass

from fs_notifications_challenge.application.ports import UserRepository
from fs_notifications_challenge.domain.errors import NotFoundError


@dataclass
class DeleteUserProfile:
    """Remove a user's profile (their saaved contact details). The user stays:
    the account, the login and the notification are untoched."""

    repository: UserRepository

    async def execute(self, user_id: int) -> None:
        user = await self.repository.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        if user.profile is None:
            raise NotFoundError(f"User {user_id} has no profile.")
        user.remove_profile()
        await self.repository.update(user)
