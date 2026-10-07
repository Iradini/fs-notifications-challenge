from dataclasses import dataclass

from fs_notifications_challenge.application.ports import UserRepository
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.errors import NotFoundError
from fs_notifications_challenge.domain.user import User, UserProfile


@dataclass
class SaveUserProfile:
    """Create or replace a user's profile (1:1, so PUT semantics)."""

    repository: UserRepository

    async def execute(self, user_id: int, contact: ContactInfo) -> User:
        user = await self.repository.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        user.profile = await self.repository.save_profile(UserProfile(user_id=user_id, contact=contact))
        return user