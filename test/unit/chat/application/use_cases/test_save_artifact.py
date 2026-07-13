from chat.application.use_cases.save_artifact import SaveArtifact
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.infrastructure.persistence.in_memory_artifact_repository import (
    InMemoryArtifactRepository,
)


def _spec() -> RenderTree:
    return RenderTree(
        root="root", elements={"root": RenderElement(type="Stack", props={}, children=[])}
    )


class TestSaveArtifact:
    def test_persists_the_artifact_and_returns_its_id(self) -> None:
        repo = InMemoryArtifactRepository()
        artifact_id = SaveArtifact(repo).execute("u-1", "Revenue overview", _spec())
        saved = repo.get(artifact_id, "u-1")
        assert saved is not None
        assert saved.title == "Revenue overview"

    def test_starts_the_artifact_at_a_single_initial_version(self) -> None:
        repo = InMemoryArtifactRepository()
        artifact_id = SaveArtifact(repo).execute("u-1", "T", _spec())
        saved = repo.get(artifact_id, "u-1")
        assert saved is not None
        assert len(saved.versions) == 1
        assert saved.versions[0].instruction is None

    def test_scopes_the_new_artifact_to_the_caller(self) -> None:
        repo = InMemoryArtifactRepository()
        artifact_id = SaveArtifact(repo).execute("alice", "T", _spec())
        assert repo.get(artifact_id, "bob") is None
