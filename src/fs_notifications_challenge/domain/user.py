from __future__ import annotations

from dataclasses import dataclass
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.errors import DomainError


@dataclass
class UserProfile():
    """A user's own contact details (1:1 with User)."""
    user_id: int
    contact: ContactInfo
    id: int | None = None


    def __post_init__(self) -> None:
        self._check_contact(self.contact)
        

    @staticmethod
    def _check_contact(contact: ContactInfo) -> None:
        if contact.is_empty:
            raise DomainError("A profile requires at least one email, one phone, and one token.")


    def replace_contact(self, contact: ContactInfo) -> None:
        """ContactInfo is frozen (a value object), so it is replaced, never edited
        field by field. Validate first, then assign: a rejected change leaves the
        profile untoched."""
        self._check_contact(contact)
        self.contact = contact


@dataclass
class User():
    """Identity. HAS a profile"""

    email: str
    password_hash: str
    id: int | None = None
    profile: UserProfile | None = None


    def __post_init__(self) -> None:
        self._check_email(self.email)
            


    @staticmethod
    def _check_email(email: str) -> None:
        if not email.strip():
            raise DomainError("User email cannot be blank.")


    def change_email(self, email: str) -> None:
        email = email.strip()
        self._check_email(email)
        self.email = email


    def change_password(self, password_hash: str) -> None:
        """Takes the already hashed password: hashing is the PasswordHasher port's"
        job, so the entity never sees (or stores) a plain password."""
        if not password_hash.strip():
            raise DomainError("Password hash cannot be blank.")
        self.password_hash = password_hash


    def set_profile(self, contact: ContactInfo) -> None:
        """Create the profile, or replace its contact (it's 1:1)."""
        if self.profile is None:
            self.profile = UserProfile(user_id=self.id, contact=contact)
        else:
            self.profile.replace_contact(contact)


    def remove_profile(self) -> None:
        """No profile = absence (None), never an empty profile. Idempotent."""
        self.profile = None 