import pytest

from chat.domain.entities.artifact import Artifact
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from shared.domain.errors import InvariantViolationError


def _spec(marker: str) -> RenderTree:
    root = RenderElement(type="Stack", props={"marker": marker}, children=[])
    return RenderTree(root="root", elements={"root": root})


def _artifact(marker: str = "v0", created_at: float = 100.0) -> Artifact:
    return Artifact.create("a-1", "u-1", "Revenue", _spec(marker), created_at)


class TestArtifactCreate:
    def test_starts_with_one_version_pointed_at_current(self) -> None:
        artifact = _artifact()
        assert len(artifact.versions) == 1
        assert artifact.current == 0
        assert artifact.versions[0].instruction is None
        assert artifact.updated_at == 100.0

    def test_current_spec_is_the_seeded_spec(self) -> None:
        artifact = _artifact("first")
        assert artifact.current_spec.elements["root"].props["marker"] == "first"


class TestAppendVersion:
    def test_appends_and_advances_the_pointer_to_the_tip(self) -> None:
        artifact = _artifact("v0")
        artifact.append_version(_spec("v1"), "make it a line chart", 200.0)
        assert len(artifact.versions) == 2
        assert artifact.current == 1
        assert artifact.current_spec.elements["root"].props["marker"] == "v1"
        assert artifact.versions[1].instruction == "make it a line chart"

    def test_updated_at_tracks_the_latest_version(self) -> None:
        artifact = _artifact(created_at=100.0)
        artifact.append_version(_spec("v1"), "edit", 250.0)
        assert artifact.updated_at == 250.0


class TestSetCurrent:
    def test_revert_is_non_destructive_and_forward_remains_reachable(self) -> None:
        artifact = _artifact("v0")
        artifact.append_version(_spec("v1"), "edit", 200.0)
        artifact.set_current(0)  # revert to the original
        assert artifact.current == 0
        assert artifact.current_spec.elements["root"].props["marker"] == "v0"
        assert len(artifact.versions) == 2  # the later version was not dropped
        artifact.set_current(1)  # step forward again
        assert artifact.current_spec.elements["root"].props["marker"] == "v1"

    def test_out_of_range_index_raises_with_the_offending_value(self) -> None:
        artifact = _artifact()
        with pytest.raises(InvariantViolationError) as exc:
            artifact.set_current(5)
        assert "5" in str(exc.value)

    def test_negative_index_raises(self) -> None:
        artifact = _artifact()
        with pytest.raises(InvariantViolationError):
            artifact.set_current(-1)
