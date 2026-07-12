from shared.infrastructure.api.current_user import ResolveOwnerId


def fake_owner_id(user_id: str = "u-1") -> ResolveOwnerId:
    """Build a ``ResolveOwnerId`` dependency resolving every request to a fixed id."""

    async def resolve() -> str:
        return user_id

    return resolve
