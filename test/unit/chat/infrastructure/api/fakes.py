from shared.application.ports.current_user import CurrentUser


class FakeCurrentUser(CurrentUser):
    """Test ``CurrentUser`` resolving every request to a fixed user id."""

    def __init__(self, user_id: str = "u-1") -> None:
        self._user_id = user_id

    async def __call__(self) -> str:
        return self._user_id
