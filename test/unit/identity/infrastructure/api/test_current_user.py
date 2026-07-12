import asyncio

from identity.infrastructure.api.current_user import (
    _bearer,
    build_owner_id_resolver,
    build_principal_resolver,
)
from identity.infrastructure.auth.guest_authenticator import GuestAuthenticator
from identity.infrastructure.persistence.in_memory_user_repository import (
    InMemoryUserRepository,
)


def _authenticator() -> GuestAuthenticator:
    return GuestAuthenticator(InMemoryUserRepository(), "guest", "Guest")


class TestBearerExtraction:
    def test_strips_the_bearer_prefix(self) -> None:
        assert _bearer("Bearer abc.def.ghi") == "abc.def.ghi"

    def test_returns_none_without_a_bearer_scheme(self) -> None:
        # a bare or non-bearer header carries no token we understand
        assert _bearer("abc.def.ghi") is None
        assert _bearer(None) is None

    def test_returns_none_for_an_empty_bearer_value(self) -> None:
        assert _bearer("Bearer   ") is None


class TestOwnerIdResolver:
    def test_missing_header_resolves_to_the_guest_id(self) -> None:
        resolve = build_owner_id_resolver(_authenticator())
        assert asyncio.run(resolve(authorization=None)) == "guest"

    def test_bearer_header_still_resolves_to_guest_in_the_guest_phase(self) -> None:
        # the guest authenticator ignores the token; the id is always the guest's
        resolve = build_owner_id_resolver(_authenticator())
        assert asyncio.run(resolve(authorization="Bearer some-token")) == "guest"


class TestPrincipalResolver:
    def test_resolves_the_full_guest_principal(self) -> None:
        resolve = build_principal_resolver(_authenticator())
        principal = asyncio.run(resolve(authorization=None))
        assert (principal.user_id, principal.email, principal.is_guest) == ("guest", None, True)
