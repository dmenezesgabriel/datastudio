import asyncio
from collections.abc import AsyncIterator
from typing import cast

import pytest

from chat.application.ports.edit_dashboard_port import EditDashboardPort
from chat.application.use_cases.edit_artifact import EditArtifact
from chat.domain.entities.artifact import Artifact
from chat.domain.errors import ArtifactNotFoundError
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.stream_event import ChatStreamEvent, ProgressStep, ViewPatchLine
from chat.infrastructure.persistence.in_memory_artifact_repository import (
    InMemoryArtifactRepository,
)
from chat.infrastructure.view.dashboard_view_builder import SpecStreamDashboardViewBuilder

_KIND_TO_LINE = '{"op":"replace","path":"/elements/widget-0-chart/props/kind","value":"line"}'


def _dashboard() -> RenderTree:
    return RenderTree(
        root="root",
        elements={
            "root": RenderElement(type="Stack", props={}, children=["widget-0-chart"]),
            "widget-0-chart": RenderElement(type="ChartJs", props={"kind": "bar"}, children=[]),
        },
    )


class FakeEditDashboardEngine:
    """Edit engine yielding fixed stream events and recording what it was asked to edit."""

    def __init__(self, events: list[ChatStreamEvent]) -> None:
        self._events = events
        self.seen_specs: list[RenderTree] = []
        self.seen_instructions: list[str] = []

    async def edit(self, spec: RenderTree, instruction: str) -> AsyncIterator[ChatStreamEvent]:
        self.seen_specs.append(spec)
        self.seen_instructions.append(instruction)
        for event in self._events:
            yield event


def _repo_with_artifact() -> InMemoryArtifactRepository:
    repo = InMemoryArtifactRepository()
    repo.save(Artifact.create("a-1", "u-1", "Revenue", _dashboard(), 1.0))
    return repo


def _use_case(repo: InMemoryArtifactRepository, engine: FakeEditDashboardEngine) -> EditArtifact:
    return EditArtifact(repo, cast(EditDashboardPort, engine), SpecStreamDashboardViewBuilder())


def _drain(
    use_case: EditArtifact, owner: str, artifact_id: str, instruction: str
) -> list[ChatStreamEvent]:
    async def run() -> list[ChatStreamEvent]:
        return [event async for event in use_case.execute(owner, artifact_id, instruction)]

    return asyncio.run(run())


class TestEditArtifact:
    def test_records_a_new_version_from_the_edit_patches(self) -> None:
        repo = _repo_with_artifact()
        engine = FakeEditDashboardEngine([ViewPatchLine(line=_KIND_TO_LINE)])
        _drain(_use_case(repo, engine), "u-1", "a-1", "make it a line chart")
        artifact = repo.get("a-1", "u-1")
        assert artifact is not None
        assert len(artifact.versions) == 2
        assert artifact.current_spec.elements["widget-0-chart"].props["kind"] == "line"
        assert artifact.versions[1].instruction == "make it a line chart"

    def test_forwards_events_to_the_caller(self) -> None:
        engine = FakeEditDashboardEngine([ViewPatchLine(line=_KIND_TO_LINE)])
        events = _drain(_use_case(_repo_with_artifact(), engine), "u-1", "a-1", "edit")
        assert [type(e).__name__ for e in events] == ["ViewPatchLine"]

    def test_seeds_the_engine_with_the_current_spec(self) -> None:
        engine = FakeEditDashboardEngine([ViewPatchLine(line=_KIND_TO_LINE)])
        _drain(_use_case(_repo_with_artifact(), engine), "u-1", "a-1", "edit")
        assert engine.seen_specs[0].elements["widget-0-chart"].props["kind"] == "bar"

    def test_missing_or_foreign_artifact_raises_not_found(self) -> None:
        engine = FakeEditDashboardEngine([ViewPatchLine(line=_KIND_TO_LINE)])
        with pytest.raises(ArtifactNotFoundError):
            _drain(_use_case(_repo_with_artifact(), engine), "someone-else", "a-1", "edit")

    def test_no_op_edit_records_no_new_version(self) -> None:
        # The engine emits only progress (no patches) — nothing to version.
        repo = _repo_with_artifact()
        engine = FakeEditDashboardEngine([ProgressStep("classify_edit", "Working", "done")])
        _drain(_use_case(repo, engine), "u-1", "a-1", "no change")
        artifact = repo.get("a-1", "u-1")
        assert artifact is not None
        assert len(artifact.versions) == 1
