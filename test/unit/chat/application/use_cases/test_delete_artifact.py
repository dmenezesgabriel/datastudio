from chat.application.use_cases.delete_artifact import DeleteArtifact
from chat.domain.entities.artifact import Artifact
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.infrastructure.persistence.in_memory_artifact_repository import (
    InMemoryArtifactRepository,
)


def _spec() -> RenderTree:
    return RenderTree(
        root="root", elements={"root": RenderElement(type="Stack", props={}, children=[])}
    )


class TestDeleteArtifact:
    def test_removes_the_artifact(self) -> None:
        repo = InMemoryArtifactRepository()
        repo.save(Artifact.create("a-1", "u-1", "T", _spec(), 1.0))
        DeleteArtifact(repo).execute("u-1", "a-1")
        assert repo.get("a-1", "u-1") is None

    def test_scopes_delete_to_the_owner(self) -> None:
        # A foreign owner cannot delete another user's artifact — it survives untouched.
        repo = InMemoryArtifactRepository()
        repo.save(Artifact.create("a-1", "alice", "T", _spec(), 1.0))
        DeleteArtifact(repo).execute("bob", "a-1")
        assert repo.get("a-1", "alice") is not None
