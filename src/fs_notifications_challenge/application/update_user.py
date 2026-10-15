from dataclasses import dataclass

from fs_notifications_challenge.application.ports import UserRepository
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.errors import ConflictError, NotFoundError
from fs_notifications_challenge.domain.user import User


@dataclass
class UpdateUser:
    """Persists the user's new email and contact information, if available."""

    repository: UserRepository

    async def execute(
            self, user_id: int, *, email: str | None = None, contact: ContactInfo | None = None,
    ) -> User:
        user = await self.repository.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        
        if email is not None:
            user.change_email(email)     # blank -> DomainError, before any query
            owner = await self.repository.get_by_email(user.email)
            # Your own current email is not a conflict (e.g. you only change the contact)
            if owner is not None and owner.id != user.id:
                raise ConflictError(f"A user with {user.email} already exists.")
        
        if contact is not None:
            user.set_profile(contact)
            
        return await self.repository.update(user)
