"""Port interface for resolving a caller's credential into a Principal."""

from typing import Protocol, runtime_checkable

from identity.domain.value_objects.principal import Principal


@runtime_checkable
class Authenticator(Protocol):
    """Turns a request credential into the :class:`Principal` making the request.

    The single swap-point for the auth mechanism: ``GuestAuthenticator`` today
    ignores the credential and returns a guest; a future ``MsalAuthenticator`` /
    ``OidcAuthenticator`` validates the bearer token and maps its ``sub`` claim to
    a :class:`~identity.domain.entities.user.User`. Async so a JWKS-validating
    adapter (network I/O) fits the same contract.

    Example:
        principal = await authenticator.authenticate(bearer_token)
    """

    async def authenticate(self, _credential: str | None) -> Principal:
        """Resolve the caller from a bearer credential (``None`` → the guest principal)."""
        ...
