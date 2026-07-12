from fastapi import FastAPI
from fastapi.testclient import TestClient

from identity.infrastructure.api.current_user import ResolveCurrentPrincipal
from identity.infrastructure.api.me_router import MeRouter
from identity.infrastructure.auth.guest_authenticator import GuestAuthenticator
from identity.infrastructure.persistence.in_memory_user_repository import (
    InMemoryUserRepository,
)


def _client() -> TestClient:
    auth = GuestAuthenticator(InMemoryUserRepository(), "guest", "Guest")
    app = FastAPI()
    app.include_router(MeRouter(ResolveCurrentPrincipal(auth)).router)
    return TestClient(app)


class TestMeRouter:
    def test_returns_the_guest_identity_without_a_token(self) -> None:
        # act
        body = _client().get("/api/me").json()
        # assert — the shape a client reads to learn who it is
        assert body == {"user_id": "guest", "display_name": "Guest", "is_guest": True}
