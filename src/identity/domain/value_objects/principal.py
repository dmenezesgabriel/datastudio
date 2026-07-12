"""Principal: the authenticated actor of the current request."""

from dataclasses import dataclass

from identity.domain.entities.user import User


@dataclass(frozen=True)
class Principal:
    """The user making the current request, resolved from their credentials.

    The request-scoped identity that flows downstream (feature contexts scope
    their data by ``user_id``). Distinct from :class:`User`, the persisted
    account: a ``Principal`` is a snapshot of who is calling right now.

    Example:
        principal = Principal.for_user(user)
        assert principal.user_id == user.user_id
    """

    user_id: str
    display_name: str
    email: str | None
    is_guest: bool

    def __post_init__(self) -> None:
        """A principal without an id cannot own anything — reject it early."""
        if not self.user_id:
            raise ValueError(f"Principal.user_id must be non-empty, got {self.user_id!r}")

    @classmethod
    def for_user(cls, user: User) -> "Principal":
        """Snapshot a persisted :class:`User` as the current request's principal."""
        return cls(
            user_id=user.user_id,
            display_name=user.display_name,
            email=user.email,
            is_guest=user.is_guest,
        )
