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
