from chat.domain.entities.artifact import Artifact
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.infrastructure.persistence.in_memory_artifact_repository import (
    InMemoryArtifactRepository,
)


def _spec() -> RenderTree:
    return RenderTree(
        root="root", elements={"root": RenderElement(type="Stack", props={}, children=[])}
    )


def _artifact(artifact_id: str, owner_id: str, title: str, created_at: float) -> Artifact:
    return Artifact.create(artifact_id, owner_id, title, _spec(), created_at)


class TestInMemoryArtifactRepository:
    def test_get_returns_the_owners_artifact(self) -> None:
        repo = InMemoryArtifactRepository()
        repo.save(_artifact("a-1", "u-1", "T", 1.0))
        assert repo.get("a-1", "u-1") is not None

    def test_get_returns_none_for_a_foreign_owner(self) -> None:
        # A wrong owner is indistinguishable from an absent id (no cross-user existence leak).
        repo = InMemoryArtifactRepository()
        repo.save(_artifact("a-1", "u-1", "T", 1.0))
        assert repo.get("a-1", "u-2") is None

    def test_get_returns_none_for_an_absent_id(self) -> None:
        assert InMemoryArtifactRepository().get("missing", "u-1") is None


class TestListSummaries:
    def test_orders_most_recently_updated_first_and_scopes_by_owner(self) -> None:
        repo = InMemoryArtifactRepository()
        repo.save(_artifact("a-old", "u-1", "Old", 100.0))
        repo.save(_artifact("a-new", "u-1", "New", 300.0))
        repo.save(_artifact("a-other", "u-2", "Other", 999.0))
        summaries = repo.list_summaries("u-1")
        assert [s.artifact_id for s in summaries] == ["a-new", "a-old"]

    def test_reports_the_version_count(self) -> None:
        repo = InMemoryArtifactRepository()
        artifact = _artifact("a-1", "u-1", "T", 1.0)
        artifact.append_version(_spec(), "edit", 2.0)
        repo.save(artifact)
        assert repo.list_summaries("u-1")[0].version_count == 2


class TestDelete:
    def test_removes_the_owners_artifact(self) -> None:
        repo = InMemoryArtifactRepository()
        repo.save(_artifact("a-1", "u-1", "T", 1.0))
        repo.delete("a-1", "u-1")
        assert repo.get("a-1", "u-1") is None

    def test_ignores_a_foreign_owner(self) -> None:
        repo = InMemoryArtifactRepository()
        repo.save(_artifact("a-1", "u-1", "T", 1.0))
        repo.delete("a-1", "u-2")  # not theirs — no-op
        assert repo.get("a-1", "u-1") is not None
