import pytest

from chat.application.use_cases.set_artifact_version import SetArtifactVersion
from chat.domain.entities.artifact import Artifact
from chat.domain.errors import ArtifactNotFoundError
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.infrastructure.persistence.in_memory_artifact_repository import (
    InMemoryArtifactRepository,
)
from shared.domain.errors import InvariantViolationError


def _spec(marker: str) -> RenderTree:
    root = RenderElement(type="Stack", props={"marker": marker}, children=[])
    return RenderTree(root="root", elements={"root": root})


def _repo_with_two_versions() -> InMemoryArtifactRepository:
    repo = InMemoryArtifactRepository()
    artifact = Artifact.create("a-1", "u-1", "T", _spec("v0"), 1.0)
    artifact.append_version(_spec("v1"), "edit", 2.0)
    repo.save(artifact)
    return repo


class TestSetArtifactVersion:
    def test_points_the_artifact_at_the_chosen_version(self) -> None:
        repo = _repo_with_two_versions()
        artifact = SetArtifactVersion(repo).execute("u-1", "a-1", 0)
        assert artifact.current == 0
        assert artifact.current_spec.elements["root"].props["marker"] == "v0"

    def test_persists_the_moved_pointer(self) -> None:
        repo = _repo_with_two_versions()
        SetArtifactVersion(repo).execute("u-1", "a-1", 0)
        reloaded = repo.get("a-1", "u-1")
        assert reloaded is not None
        assert reloaded.current == 0

    def test_missing_or_foreign_artifact_raises_not_found(self) -> None:
        repo = _repo_with_two_versions()
        with pytest.raises(ArtifactNotFoundError):
            SetArtifactVersion(repo).execute("someone-else", "a-1", 0)

    def test_out_of_range_index_raises_invariant_violation(self) -> None:
        repo = _repo_with_two_versions()
        with pytest.raises(InvariantViolationError):
            SetArtifactVersion(repo).execute("u-1", "a-1", 9)
