"""Tests for the artifact CRUD API (gallery list, open, versions, revert, delete)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chat.application.use_cases.save_artifact import SaveArtifact
from chat.application.use_cases.set_artifact_version import SetArtifactVersion
from chat.domain.entities.artifact import Artifact
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.infrastructure.api.artifacts_router import ArtifactsRouter
from chat.infrastructure.persistence.in_memory_artifact_repository import (
    InMemoryArtifactRepository,
)
from shared.infrastructure.api.error_handlers import register_error_handlers
from test.unit.chat.infrastructure.api.fakes import fake_owner_id

_OWNER = "u-1"


def _spec(marker: str = "v0") -> RenderTree:
    root = RenderElement(type="Stack", props={"marker": marker}, children=[])
    return RenderTree(root="root", elements={"root": root})


def _client(repo: InMemoryArtifactRepository, user_id: str = _OWNER) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)  # so ArtifactNotFound -> 404, InvariantViolation -> 422
    router = ArtifactsRouter(
        repo, SaveArtifact(repo), SetArtifactVersion(repo), fake_owner_id(user_id)
    ).router
    app.include_router(router)
    return TestClient(app)


def _save(client: TestClient, title: str = "Revenue") -> str:
    body = {"title": title, "spec": _spec().model_dump()}
    return client.post("/api/artifacts", json=body).json()["artifact_id"]


class TestSaveAndList:
    def test_saved_artifact_appears_in_the_gallery(self) -> None:
        client = _client(InMemoryArtifactRepository())
        artifact_id = _save(client, "Revenue overview")
        listing = client.get("/api/artifacts").json()["artifacts"]
        assert listing[0]["artifact_id"] == artifact_id
        assert listing[0]["title"] == "Revenue overview"


class TestOpenAndVersions:
    def test_get_returns_current_spec_and_history(self) -> None:
        client = _client(InMemoryArtifactRepository())
        artifact_id = _save(client)
        body = client.get(f"/api/artifacts/{artifact_id}").json()
        assert body["current"] == 0
        assert body["spec"]["root"] == "root"
        assert len(body["versions"]) == 1

    def test_get_out_of_range_version_is_404(self) -> None:
        client = _client(InMemoryArtifactRepository())
        artifact_id = _save(client)
        assert client.get(f"/api/artifacts/{artifact_id}/versions/9").status_code == 404


class TestRevert:
    def _repo_with_two_versions(self) -> InMemoryArtifactRepository:
        repo = InMemoryArtifactRepository()
        artifact = Artifact.create("a-1", _OWNER, "T", _spec("v0"), 1.0)
        artifact.append_version(_spec("v1"), "edit", 2.0)
        repo.save(artifact)
        return repo

    def test_revert_points_at_the_chosen_version(self) -> None:
        client = _client(self._repo_with_two_versions())
        body = client.post("/api/artifacts/a-1/revert", json={"index": 0}).json()
        assert body["current"] == 0
        assert body["spec"]["elements"]["root"]["props"]["marker"] == "v0"

    def test_revert_out_of_range_is_422(self) -> None:
        client = _client(self._repo_with_two_versions())
        assert client.post("/api/artifacts/a-1/revert", json={"index": 9}).status_code == 422


class TestDeleteAndScoping:
    def test_delete_then_get_is_404(self) -> None:
        client = _client(InMemoryArtifactRepository())
        artifact_id = _save(client)
        client.delete(f"/api/artifacts/{artifact_id}")
        assert client.get(f"/api/artifacts/{artifact_id}").status_code == 404

    def test_a_foreign_owner_cannot_open_the_artifact(self) -> None:
        repo = InMemoryArtifactRepository()
        repo.save(Artifact.create("a-1", "alice", "T", _spec(), 1.0))
        bobs_client = _client(repo, user_id="bob")
        assert bobs_client.get("/api/artifacts/a-1").status_code == 404
