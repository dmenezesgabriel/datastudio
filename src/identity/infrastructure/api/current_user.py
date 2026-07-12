"""HTTP seam: resolve the current request's user from the Authorization header.

Adapts the :class:`~identity.application.ports.authenticator.Authenticator` to
FastAPI. ``ResolveCurrentUser`` returns just the ``user_id`` and is the
dependency feature contexts (chat) consume via the shared ``CurrentUser`` port;
``ResolveCurrentPrincipal`` returns the full principal for identity's own
``/api/me``. Both are FastAPI dependencies (callable instances whose ``__call__``
declares the header parameter FastAPI injects).
"""

from fastapi import Header

from identity.application.ports.authenticator import Authenticator
from identity.domain.value_objects.principal import Principal
from shared.application.ports.current_user import CurrentUser

_BEARER_PREFIX = "Bearer "


def _bearer(authorization: str | None) -> str | None:
    """Extract the raw bearer token from an ``Authorization`` header value, if present."""
    if authorization is None or not authorization.startswith(_BEARER_PREFIX):
        return None
    return authorization[len(_BEARER_PREFIX) :].strip() or None


class ResolveCurrentUser(CurrentUser):
    """FastAPI dependency yielding the current request's ``user_id``.

    Implements the shared ``CurrentUser`` port so chat can depend on it without
    importing this component.

    Example:
        resolve = ResolveCurrentUser(authenticator)
        user_id = await resolve()  # or Depends(resolve) in a route
    """

    def __init__(self, authenticator: Authenticator) -> None:
        """Wire the authenticator that turns the bearer token into a principal."""
        self._authenticator = authenticator

    async def __call__(self, authorization: str | None = Header(default=None)) -> str:
        """Resolve the caller and return their id (the guest id when unauthenticated)."""
        principal = await self._authenticator.authenticate(_bearer(authorization))
        return principal.user_id


class ResolveCurrentPrincipal:
    """FastAPI dependency yielding the full current :class:`Principal` (for ``/api/me``)."""

    def __init__(self, authenticator: Authenticator) -> None:
        """Wire the authenticator that turns the bearer token into a principal."""
        self._authenticator = authenticator

    async def __call__(self, authorization: str | None = Header(default=None)) -> Principal:
        """Resolve and return the caller's principal (the guest when unauthenticated)."""
        return await self._authenticator.authenticate(_bearer(authorization))
