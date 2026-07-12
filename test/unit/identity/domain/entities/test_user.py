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


class TestUserForSubject:
    def test_account_linked_to_a_subject_is_not_a_guest(self) -> None:
        # arrange / act — an account minted from an IdP subject (the OIDC ``sub``)
        alice = User.for_subject("u-42", "Alice", subject="entra|abc123")
        # assert
        assert alice.subject == "entra|abc123"
        assert alice.is_guest is False
