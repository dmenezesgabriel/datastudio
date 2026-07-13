"""Tests for the streaming artifact-edit API and its request contract.

Regression guard: json-render's ``useUIStream`` POSTs ``{prompt, context, currentSpec}``,
so the endpoint must read ``prompt`` (not a bespoke field) or the browser edit 422s.
"""

from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chat.application.use_cases.edit_artifact import EditArtifact
from chat.domain.entities.artifact import Artifact
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.stream_event import ChatStreamEvent, NarrativeReady
from chat.infrastructure.api.artifact_edit_router import ArtifactEditRouter
from chat.infrastructure.persistence.in_memory_artifact_repository import (
    InMemoryArtifactRepository,
)
from shared.infrastructure.api.error_handlers import register_error_handlers
from test.unit.chat.infrastructure.api.fakes import fake_owner_id

_OWNER = "u-1"


class FakeEditArtifact:
    """Records the instruction it was driven with; streams a single narrative event."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def execute(
        self, owner_id: str, artifact_id: str, instruction: str
    ) -> AsyncIterator[ChatStreamEvent]:
        self.calls.append((owner_id, artifact_id, instruction))
        yield NarrativeReady(text="done")


def _spec() -> RenderTree:
    return RenderTree(
        root="root", elements={"root": RenderElement(type="Stack", props={}, children=[])}
    )


def _repo_with_artifact() -> InMemoryArtifactRepository:
    repo = InMemoryArtifactRepository()
    repo.save(Artifact.create("a-1", _OWNER, "T", _spec(), 1.0))
    return repo


def _client(edit_artifact: FakeEditArtifact, repo: InMemoryArtifactRepository) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    router = ArtifactEditRouter(
        cast(EditArtifact, edit_artifact), repo, fake_owner_id(_OWNER)
    ).router
    app.include_router(router)
    return TestClient(app)


class TestArtifactEditRouter:
    def test_accepts_the_useuistream_prompt_body_and_drives_the_use_case(self) -> None:
        # Regression: the browser sends {prompt, context, currentSpec}; the endpoint reads prompt.
        edit = FakeEditArtifact()
        client = _client(edit, _repo_with_artifact())
        body = {"prompt": "make it a line chart", "context": {}, "currentSpec": {"x": 1}}
        response = client.post("/api/artifacts/a-1/edit", json=body)
        assert response.status_code == 200
        assert edit.calls == [(_OWNER, "a-1", "make it a line chart")]

    def test_body_without_prompt_is_422(self) -> None:
        client = _client(FakeEditArtifact(), _repo_with_artifact())
        response = client.post("/api/artifacts/a-1/edit", json={"instruction": "x"})
        assert response.status_code == 422

    def test_missing_artifact_is_404_before_streaming(self) -> None:
        client = _client(FakeEditArtifact(), InMemoryArtifactRepository())
        response = client.post("/api/artifacts/missing/edit", json={"prompt": "x"})
        assert response.status_code == 404
