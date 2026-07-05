"""App-boot e2e for the composition root: route aggregation, no SPA mount, read path."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bootstrap import create_app


@pytest.fixture
def offline_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Build the real object graph offline: dummy key + throwaway duckdb, no network."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "e2e.duckdb"))


class TestCreateApp:
    def test_mounts_every_component_route(self, offline_env: None) -> None:
        # arrange / act
        app = create_app()
        paths = set(app.openapi()["paths"])
        # assert
        assert {
            "/api/chat",
            "/api/conversations",
            "/api/conversations/{conversation_id}",
        } <= paths

    def test_does_not_serve_a_frontend_spa(self, offline_env: None) -> None:
        # the backend no longer mounts the SPA — root falls through to 404
        client = TestClient(create_app())
        assert client.get("/").status_code == 404

    def test_conversations_read_path_returns_empty_list(self, offline_env: None) -> None:
        # a real HTTP request through the assembled backend + real chat composition
        client = TestClient(create_app())
        response = client.get("/api/conversations")
        assert response.status_code == 200
        assert response.json() == {"conversations": []}
