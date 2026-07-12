"""HTTP seam: resolve the current request's user from the Authorization header.

Adapts the :class:`~identity.application.ports.authenticator.Authenticator` to
FastAPI. ``build_owner_id_resolver`` yields just the ``user_id`` and is the
dependency feature contexts (chat) consume via the shared ``ResolveOwnerId``
seam; ``build_principal_resolver`` yields the full principal for identity's own
``/api/me``. Each returns a FastAPI dependency (an async callable whose
``authorization`` parameter FastAPI injects from the header).
"""

from fastapi import Header

from identity.application.ports.authenticator import Authenticator
from identity.domain.value_objects.principal import Principal
from identity.infrastructure.types import ResolvePrincipal
from shared.infrastructure.api.current_user import ResolveOwnerId

_BEARER_PREFIX = "Bearer "


def _bearer(authorization: str | None) -> str | None:
    """Extract the raw bearer token from an ``Authorization`` header value, if present."""
    if authorization is None or not authorization.startswith(_BEARER_PREFIX):
        return None
    return authorization[len(_BEARER_PREFIX) :].strip() or None


async def _principal(authenticator: Authenticator, authorization: str | None) -> Principal:
    """Resolve the caller's principal from a raw ``Authorization`` header value."""
    return await authenticator.authenticate(_bearer(authorization))


def build_principal_resolver(authenticator: Authenticator) -> ResolvePrincipal:
    """Build the ``/api/me`` dependency: resolve the full current :class:`Principal`.

    Example:
        resolve = build_principal_resolver(authenticator)
        principal = await resolve(authorization="Bearer <token>")
    """

    async def resolve(authorization: str | None = Header(default=None)) -> Principal:
        return await _principal(authenticator, authorization)

    return resolve


def build_owner_id_resolver(authenticator: Authenticator) -> ResolveOwnerId:
    """Build the shared dependency feature contexts consume: the current ``user_id``.

    Example:
        resolve = build_owner_id_resolver(authenticator)
        user_id = await resolve(authorization=None)  # the guest id when unauthenticated
    """

    async def resolve(authorization: str | None = Header(default=None)) -> str:
        return (await _principal(authenticator, authorization)).user_id

    return resolve
