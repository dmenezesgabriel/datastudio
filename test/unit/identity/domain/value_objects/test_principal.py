import pytest

from identity.domain.entities.user import User
from identity.domain.value_objects.principal import Principal


class TestPrincipalForUser:
    def test_snapshots_a_guest_user(self) -> None:
        # arrange / act
        principal = Principal.for_user(User.guest("guest", "Guest"))
        # assert
        assert principal == Principal(
            user_id="guest", display_name="Guest", email=None, is_guest=True
        )

    def test_snapshots_an_authenticated_user(self) -> None:
        principal = Principal.for_user(
            User.for_subject("u-42", "Alice", "entra|abc", email="alice@corp.com")
        )
        assert principal.user_id == "u-42"
        assert principal.email == "alice@corp.com"
        assert principal.is_guest is False


class TestPrincipalValidation:
    def test_rejects_empty_user_id(self) -> None:
        # a principal without an id could own nothing — construction must fail loudly
        with pytest.raises(ValueError, match="user_id must be non-empty"):
            Principal(user_id="", display_name="Nobody", email=None, is_guest=True)
