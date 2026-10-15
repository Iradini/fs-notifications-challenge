from dataclasses import dataclass

from fs_notifications_challenge.application.ports import PasswordHasher, UserRepository
from fs_notifications_challenge.domain.errors import DomainError, NotFoundError


@dataclass
class DeleteUser:
    """Permanently erase the account. Unlike a notification (soft delete, kept for 
    audit), this is a real delete: the user, their contact info, every notification
    (deleted ones too), and the outbox rows and delivery attempts that hang from them.
    Asks for the password again, as for any irreversible step."""

    repository: UserRepository
    hasher: PasswordHasher

    async def execute(self, user_id: int, password: str) -> None:
        user = await self.repository.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        if not user.password_hash or not self.hasher.verify_password(password, user.password_hash):
            raise DomainError("Incorrect password.")
        await self.repository.delete(user)