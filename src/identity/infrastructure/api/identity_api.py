"""HTTP assembly seam for the identity component.

Self-contained wiring for identity's FastAPI surface. ``build_identity_api``
composes the object graph from settings and returns an :class:`IdentityApi`: the
``resolve_current_user`` dependency other components consume to scope their data,
plus identity's own routers. The composition root (``bootstrap.py``) mounts the
routers and injects the dependency into feature components.
"""

from dataclasses import dataclass

from fastapi import APIRouter

from identity.infrastructure.api.current_user import (
    build_owner_id_resolver,
    build_principal_resolver,
)
from identity.infrastructure.api.me_router import MeRouter
from identity.infrastructure.auth.guest_authenticator import GuestAuthenticator
from identity.infrastructure.persistence.in_memory_user_repository import (
    InMemoryUserRepository,
)
from shared.infrastructure.api.current_user import ResolveOwnerId
from shared.infrastructure.config.settings import AppSettings


@dataclass(frozen=True)
class IdentityApi:
    """Identity's HTTP surface: the current-user dependency plus its own routers.

    ``resolve_current_user`` is injected into feature components so they scope
    data by owner without importing identity; ``routers`` are mounted by the
    composition root.
    """

    resolve_current_user: ResolveOwnerId
    routers: list[APIRouter]


def build_identity_api(settings: AppSettings) -> IdentityApi:
    """Compose identity's HTTP surface from settings (guest authentication for now).

    Example:
        identity = build_identity_api(AppSettings())
        for router in identity.routers:
            app.include_router(router)
    """
    users = InMemoryUserRepository()
    authenticator = GuestAuthenticator(users, settings.guest_user_id, settings.guest_display_name)
    routers = [MeRouter(build_principal_resolver(authenticator)).router]
    return IdentityApi(build_owner_id_resolver(authenticator), routers)
