from identity.domain.entities.user import User
from identity.infrastructure.persistence.in_memory_user_repository import (
    InMemoryUserRepository,
)


class TestInMemoryUserRepository:
    def test_save_then_get_round_trip(self) -> None:
        # arrange
        repository = InMemoryUserRepository()
        user = User.guest("guest", "Guest")
        # act
        repository.save(user)
        # assert
        assert repository.get("guest") is user

    def test_get_missing_returns_none(self) -> None:
        assert InMemoryUserRepository().get("absent") is None

    def test_find_by_subject_returns_the_linked_account(self) -> None:
        # arrange — the seam a real IdP uses to upsert on first sign-in
        repository = InMemoryUserRepository()
        alice = User.for_subject("u-42", "Alice", "entra|abc")
        repository.save(alice)
        # act / assert
        assert repository.find_by_subject("entra|abc") is alice

    def test_find_by_subject_missing_returns_none(self) -> None:
        repository = InMemoryUserRepository()
        repository.save(User.guest("guest", "Guest"))  # guest has no subject
        assert repository.find_by_subject("entra|abc") is None
