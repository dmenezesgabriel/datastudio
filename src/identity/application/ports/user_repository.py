"""Port interface for user-account persistence."""

from typing import Protocol, runtime_checkable

from identity.domain.entities.user import User


@runtime_checkable
class UserRepository(Protocol):
    """Contract for storing and retrieving user accounts.

    Example:
        repo: UserRepository = InMemoryUserRepository()
        repo.save(user)
        same = repo.get(user.user_id)
    """

    def get(self, user_id: str) -> User | None:
        """Return the account for the id, or None if absent."""
        ...

    def save(self, user: User) -> None:
        """Persist the account, overwriting any prior state for its id."""
        ...
