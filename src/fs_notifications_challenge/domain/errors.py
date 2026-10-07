class DomainError(Exception):
    """A business rule was violated (-> 422)."""


class NotFoundError(DomainError):
    """The requested entity doesn't exist (-> 404)"""


class ConflictError(DomainError):
    """The request conflicts with the entity's current state (-> 409)."""


class ConcurrentUpdateError(ConflictError):
    """Someone else changed the entity between our read and our write.
    Raised by repositories so callers never see ORM-specific exceptions."""