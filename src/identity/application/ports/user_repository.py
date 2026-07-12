"""Port interface for user-account persistence."""

from typing import Protocol, runtime_checkable

from identity.domain.entities.user import User


@runtime_checkable
class UserRepository(Protocol):
    """Contract for storing and retrieving user accounts.

    ``find_by_subject`` is the seam a real IdP adapter uses to upsert an account
    on first sign-in (look up by the OIDC ``sub``, create if absent). The guest
    flow does not use it, but the port carries it so swapping in OIDC needs no
    port change.

    Example:
        repo: UserRepository = InMemoryUserRepository()
        repo.save(user)
        same = repo.get(user.user_id)
    """

    def get(self, user_id: str) -> User | None:
        """Return the account for the id, or None if absent."""
        ...

    def find_by_subject(self, subject: str) -> User | None:
        """Return the account linked to the external IdP subject, or None if absent."""
        ...

    def save(self, user: User) -> None:
        """Persist the account, overwriting any prior state for its id."""
        ...
