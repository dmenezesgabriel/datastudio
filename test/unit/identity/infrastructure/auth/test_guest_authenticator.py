import asyncio

from identity.domain.value_objects.principal import Principal
from identity.infrastructure.auth.guest_authenticator import GuestAuthenticator
from identity.infrastructure.persistence.in_memory_user_repository import (
    InMemoryUserRepository,
)


def _authenticate(auth: GuestAuthenticator, credential: str | None) -> Principal:
    return asyncio.run(auth.authenticate(credential))


class TestGuestAuthenticator:
    def test_resolves_to_the_configured_guest_ignoring_the_credential(self) -> None:
        # arrange
        auth = GuestAuthenticator(InMemoryUserRepository(), "guest", "Guest")
        # act — even a bearer token is ignored in the guest phase
        principal = _authenticate(auth, "Bearer whatever")
        # assert
        assert principal == Principal(user_id="guest", display_name="Guest", is_guest=True)

    def test_creates_the_guest_account_on_first_use(self) -> None:
        # arrange — an empty store; the guest must be minted lazily
        users = InMemoryUserRepository()
        auth = GuestAuthenticator(users, "guest", "Guest")
        assert users.get("guest") is None
        # act
        _authenticate(auth, None)
        # assert — the guest account now exists (upsert-on-first-contact)
        stored = users.get("guest")
        assert stored is not None
        assert stored.is_guest is True

    def test_reuses_the_existing_guest_account(self) -> None:
        # arrange
        users = InMemoryUserRepository()
        auth = GuestAuthenticator(users, "guest", "Guest")
        # act — authenticate twice
        _authenticate(auth, None)
        first = users.get("guest")
        _authenticate(auth, None)
        # assert — the same account instance is kept, not recreated
        assert users.get("guest") is first
