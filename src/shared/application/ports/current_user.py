"""Port: resolve the id of the user who owns the current request.

The cross-component seam between the ``identity`` context (which provides an
implementation from the request's credentials) and any feature context that
scopes its data by owner (today: ``chat``). Kept framework-free so it lives in
the application ring — the HTTP mechanics (bearer header extraction) belong to
the concrete adapter in ``identity/infrastructure``.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class CurrentUser(Protocol):
    """Resolves the id of the user who owns the current request.

    A zero-argument async callable returning a ``user_id``. Concrete adapters may
    add framework-injected parameters (e.g. a FastAPI ``Header``) with defaults —
    they remain callable with no positional arguments, so they satisfy this port.

    Example:
        resolve: CurrentUser = ResolveCurrentUser(authenticator)
        user_id = await resolve()
    """

    async def __call__(self) -> str:
        """Return the id of the user who owns the current request."""
        ...
