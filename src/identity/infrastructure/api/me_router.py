"""FastAPI router exposing the current user (``GET /api/me``).

The identity read surface a client calls to learn who it is. Token-scoped: the
user comes from the request's credentials, never from a path segment.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from identity.domain.value_objects.principal import Principal
from identity.infrastructure.types import ResolvePrincipal


class MeRouter:
    """Builds an APIRouter returning the authenticated caller's identity.

    Example:
        router = MeRouter(resolve_principal).router
        app.include_router(router)
    """

    def __init__(self, resolve_principal: ResolvePrincipal) -> None:
        """Register ``GET /api/me`` backed by the principal-resolving dependency."""
        self.router = APIRouter()
        self._add_routes(resolve_principal)

    def _add_routes(self, resolve_principal: ResolvePrincipal) -> None:
        """Bind the route via a closure so the dependency is a valid ``Depends`` default."""

        async def me(
            principal: Annotated[Principal, Depends(resolve_principal)],
        ) -> dict[str, object]:
            return {
                "user_id": principal.user_id,
                "display_name": principal.display_name,
                "email": principal.email,
                "is_guest": principal.is_guest,
            }

        self.router.add_api_route("/api/me", me, methods=["GET"])
