from identity.domain.entities.user import User


class TestUserGuest:
    def test_guest_has_no_external_subject(self) -> None:
        # arrange / act
        guest = User.guest("guest", "Guest")
        # assert
        assert guest.subject is None
        assert guest.is_guest is True

    def test_guest_keeps_id_and_display_name(self) -> None:
        guest = User.guest("guest", "Guest")
        assert (guest.user_id, guest.display_name) == ("guest", "Guest")

    def test_guest_has_no_email(self) -> None:
        # a locally-minted guest carries no external email
        assert User.guest("guest", "Guest").email is None


class TestUserForSubject:
    def test_account_linked_to_a_subject_is_not_a_guest(self) -> None:
        # arrange / act — an account minted from an IdP subject (the OIDC ``sub``)
        alice = User.for_subject("u-42", "Alice", subject="entra|abc123", email="alice@corp.com")
        # assert
        assert alice.subject == "entra|abc123"
        assert alice.is_guest is False

    def test_account_carries_the_idp_email(self) -> None:
        alice = User.for_subject("u-42", "Alice", subject="entra|abc123", email="alice@corp.com")
        assert alice.email == "alice@corp.com"
