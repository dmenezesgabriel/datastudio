"""Tests for the streaming artifact-edit API and its request contract.

Regression guard: json-render's ``useUIStream`` POSTs ``{prompt, context, currentSpec}``,
so the endpoint must read ``prompt`` (not a bespoke field) or the browser edit 422s.
"""

import json
from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chat.application.use_cases.edit_artifact import EditArtifact
from chat.domain.entities.artifact import Artifact
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.stream_event import ChatStreamEvent, NarrativeReady, ViewPatchLine
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


class FailingEditArtifact:
    """Streams one event, then raises — the edit graph blowing up mid-stream.

    Yielding before raising is the point: the client has already received patches and
    the response headers are long gone, so the router cannot switch to a 500. It has to
    append a graceful message to the stream it is already in.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def execute(
        self, owner_id: str, artifact_id: str, instruction: str
    ) -> AsyncIterator[ChatStreamEvent]:
        self.calls.append((owner_id, artifact_id, instruction))
        yield ViewPatchLine(
            line='{"op":"replace","path":"/elements/widget-0-chart","value":{"type":"ChartJs"}}'
        )
        raise RuntimeError("edit graph exploded")


def _spec() -> RenderTree:
    return RenderTree(
        root="root", elements={"root": RenderElement(type="Stack", props={}, children=[])}
    )


def _repo_with_artifact() -> InMemoryArtifactRepository:
    repo = InMemoryArtifactRepository()
    repo.save(Artifact.create("a-1", _OWNER, "T", _spec(), 1.0))
    return repo


def _client(
    edit_artifact: FakeEditArtifact | FailingEditArtifact, repo: InMemoryArtifactRepository
) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    router = ArtifactEditRouter(
        cast(EditArtifact, edit_artifact), repo, fake_owner_id(_OWNER)
    ).router
    app.include_router(router)
    return TestClient(app)


def _stream_lines(client: TestClient) -> list[dict[str, object]]:
    with client.stream("POST", "/api/artifacts/a-1/edit", json={"prompt": "x"}) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line.strip()]


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


class TestArtifactEditRouterUseCaseFailure:
    """The graceful-degradation path: a mid-stream exception must not hang the client."""

    def test_failure_still_returns_200(self) -> None:
        # unlike the pre-stream 404, this failure happens after the headers went out
        client = _client(FailingEditArtifact(), _repo_with_artifact())
        with client.stream("POST", "/api/artifacts/a-1/edit", json={"prompt": "x"}) as response:
            assert response.status_code == 200

    def test_patches_streamed_before_the_failure_survive(self) -> None:
        patches = _stream_lines(_client(FailingEditArtifact(), _repo_with_artifact()))
        # the edit that made it out is kept — the error message is appended, not substituted
        assert any(p["path"] == "/elements/widget-0-chart" for p in patches)

    def test_appends_the_editing_error_message_last(self) -> None:
        # the wording is the edit router's own — distinct from the chat router's
        patches = _stream_lines(_client(FailingEditArtifact(), _repo_with_artifact()))
        assert patches[-1]["path"] == "/elements/narrative/props/text"
        assert patches[-1]["value"] == "Something went wrong while editing. Please try again."

    def test_every_line_including_the_error_is_a_well_formed_patch(self) -> None:
        # a half-serialized trailing line would break the client's patch application
        patches = _stream_lines(_client(FailingEditArtifact(), _repo_with_artifact()))
        assert all("op" in p and "path" in p for p in patches)
