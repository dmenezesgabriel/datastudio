"""Tests for the centralized domain-error -> HTTP translation."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.domain.errors import DomainError, InvariantViolationError, NotFoundError
from shared.infrastructure.api.error_handlers import register_error_handlers


class _ComponentNotFoundError(NotFoundError):
    """Stands in for a component subclass to prove subclasses are mapped by category."""


def _client_raising(exc: DomainError) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise exc

    return TestClient(app)


class TestDomainErrorTranslation:
    def test_not_found_maps_to_404(self) -> None:
        response = _client_raising(NotFoundError("missing thing 'x'")).get("/boom")
        assert response.status_code == 404
        assert response.json() == {"detail": "missing thing 'x'"}

    def test_component_subclass_maps_by_category(self) -> None:
        # a component-specific subclass is caught via the base registration + isinstance
        assert _client_raising(_ComponentNotFoundError("gone")).get("/boom").status_code == 404

    def test_invariant_violation_maps_to_422(self) -> None:
        assert _client_raising(InvariantViolationError("bad value")).get("/boom").status_code == 422

    def test_bare_domain_error_defaults_to_400(self) -> None:
        assert _client_raising(DomainError("generic")).get("/boom").status_code == 400
