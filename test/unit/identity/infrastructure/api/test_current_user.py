import asyncio

from identity.infrastructure.api.current_user import ResolveCurrentUser, _bearer
from identity.infrastructure.auth.guest_authenticator import GuestAuthenticator
from identity.infrastructure.persistence.in_memory_user_repository import (
    InMemoryUserRepository,
)


def _resolver() -> ResolveCurrentUser:
    auth = GuestAuthenticator(InMemoryUserRepository(), "guest", "Guest")
    return ResolveCurrentUser(auth)


class TestBearerExtraction:
    def test_strips_the_bearer_prefix(self) -> None:
        assert _bearer("Bearer abc.def.ghi") == "abc.def.ghi"

    def test_returns_none_without_a_bearer_scheme(self) -> None:
        # a bare or non-bearer header carries no token we understand
        assert _bearer("abc.def.ghi") is None
        assert _bearer(None) is None

    def test_returns_none_for_an_empty_bearer_value(self) -> None:
        assert _bearer("Bearer   ") is None


class TestResolveCurrentUser:
    def test_missing_header_resolves_to_the_guest_id(self) -> None:
        user_id = asyncio.run(_resolver()(authorization=None))
        assert user_id == "guest"

    def test_bearer_header_still_resolves_to_guest_in_the_guest_phase(self) -> None:
        # the guest authenticator ignores the token; the id is always the guest's
        user_id = asyncio.run(_resolver()(authorization="Bearer some-token"))
        assert user_id == "guest"
