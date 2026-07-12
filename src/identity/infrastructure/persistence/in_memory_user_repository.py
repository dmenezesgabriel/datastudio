"""In-memory user-account repository (process-lifetime storage)."""

from identity.application.ports.user_repository import UserRepository
from identity.domain.entities.user import User


class InMemoryUserRepository(UserRepository):
    """Stores user accounts in a dict for the lifetime of the process.

    State is lost on restart — fine for the guest-only phase. Swap for a durable
    adapter (same port) when real accounts must persist across restarts.

    Example:
        repo = InMemoryUserRepository()
        repo.save(User.guest("guest", "Guest"))
        same = repo.get("guest")
    """

    def __init__(self) -> None:
        """Start with an empty account store."""
        self._users: dict[str, User] = {}

    def get(self, user_id: str) -> User | None:
        """Return the account for the id, or None if absent."""
        return self._users.get(user_id)

    def save(self, user: User) -> None:
        """Persist the account, overwriting any prior state for its id."""
        self._users[user.user_id] = user
