"""Authenticator that resolves every caller to a single shared guest account."""

from identity.application.ports.authenticator import Authenticator
from identity.application.ports.user_repository import UserRepository
from identity.domain.entities.user import User
from identity.domain.value_objects.principal import Principal


class GuestAuthenticator(Authenticator):
    """Resolves any request to the guest account, ignoring the credential.

    The stand-in until a real IdP is wired: it takes the same "resolve the
    account, creating it on first contact" path a real adapter will (the guest is
    upserted the first time it is needed), so the seam is exercised end-to-end.

    Example:
        auth = GuestAuthenticator(users, "guest", "Guest")
        principal = await auth.authenticate(None)  # -> the guest principal
    """

    def __init__(self, users: UserRepository, guest_user_id: str, guest_display_name: str) -> None:
        """Wire the account store and the configured guest identity."""
        self._users = users
        self._guest_user_id = guest_user_id
        self._guest_display_name = guest_display_name

    async def authenticate(self, _credential: str | None) -> Principal:
        """Return the guest principal, ensuring the guest account exists first."""
        user = self._users.get(self._guest_user_id) or self._ensure_guest()
        return Principal.for_user(user)

    def _ensure_guest(self) -> User:
        """Create and persist the guest account on first use (upsert-on-first-contact)."""
        guest = User.guest(self._guest_user_id, self._guest_display_name)
        self._users.save(guest)
        return guest
