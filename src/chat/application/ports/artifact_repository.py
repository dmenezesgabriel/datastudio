"""Port interface for artifact persistence (saved, versioned dashboards)."""

from typing import Protocol, runtime_checkable

from chat.domain.entities.artifact import Artifact
from chat.domain.value_objects.artifact_summary import ArtifactSummary


@runtime_checkable
class ArtifactRepository(Protocol):
    """Contract for storing and retrieving artifacts by id.

    The whole aggregate — including its version log — is persisted and loaded as a
    unit, so revision history stays a domain concern and never leaks into this
    interface. The in-memory adapter keeps artifacts for the process lifetime; a
    durable adapter (same port) could persist them across restarts.

    Reads are scoped by ``owner_id`` so a caller only ever reaches their own
    artifacts; ``save`` needs no owner argument because it travels on the entity.

    Example:
        repo: ArtifactRepository = InMemoryArtifactRepository()
        repo.save(artifact)
        same = repo.get(artifact.artifact_id, artifact.owner_id)
    """

    def get(self, artifact_id: str, owner_id: str) -> Artifact | None:
        """Return the artifact for the id if owned by ``owner_id``, else None.

        Returns None both when the id is absent and when it belongs to another
        user — callers cannot distinguish the two (no cross-user existence leak).
        """
        ...

    def save(self, artifact: Artifact) -> None:
        """Persist the artifact, overwriting any prior state for its id."""
        ...

    def list_summaries(self, owner_id: str) -> list[ArtifactSummary]:
        """Return summaries of ``owner_id``'s artifacts, most-recently-updated first."""
        ...

    def delete(self, artifact_id: str, owner_id: str) -> None:
        """Remove the artifact if owned by ``owner_id``; a no-op otherwise."""
        ...
