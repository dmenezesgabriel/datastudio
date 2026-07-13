"""In-memory artifact repository storing saved dashboards for the process lifetime."""

from chat.application.ports.artifact_repository import ArtifactRepository
from chat.domain.entities.artifact import Artifact
from chat.domain.value_objects.artifact_summary import ArtifactSummary


class InMemoryArtifactRepository(ArtifactRepository):
    """Stores artifacts in a dict for the lifetime of the process.

    State is lost on restart. Suitable for a single-process server; swap for a
    durable adapter (same port) to persist across restarts — the aggregate is
    JSON-serializable, so that adapter is a drop-in.

    Example:
        repo = InMemoryArtifactRepository()
        repo.save(artifact)
        same = repo.get(artifact.artifact_id, artifact.owner_id)
    """

    def __init__(self) -> None:
        """Start with an empty artifact store."""
        self._artifacts: dict[str, Artifact] = {}

    def get(self, artifact_id: str, owner_id: str) -> Artifact | None:
        """Return the artifact for the id only when it belongs to ``owner_id``.

        A wrong owner is treated exactly like an absent id (returns None) so a
        caller cannot probe for other users' artifacts.
        """
        artifact = self._artifacts.get(artifact_id)
        if artifact is None or artifact.owner_id != owner_id:
            return None
        return artifact

    def save(self, artifact: Artifact) -> None:
        """Persist the artifact, overwriting any prior state for its id."""
        self._artifacts[artifact.artifact_id] = artifact

    def list_summaries(self, owner_id: str) -> list[ArtifactSummary]:
        """Summarize ``owner_id``'s artifacts, most-recently-updated first."""
        owned = [a for a in self._artifacts.values() if a.owner_id == owner_id]
        return sorted((self._summarize(a) for a in owned), key=lambda s: s.updated_at, reverse=True)

    def delete(self, artifact_id: str, owner_id: str) -> None:
        """Remove the artifact when owned by ``owner_id``; ignore absent/foreign ids."""
        if self.get(artifact_id, owner_id) is not None:
            del self._artifacts[artifact_id]

    def _summarize(self, artifact: Artifact) -> ArtifactSummary:
        """Build a gallery summary from a stored artifact."""
        return ArtifactSummary(
            artifact_id=artifact.artifact_id,
            title=artifact.title,
            updated_at=artifact.updated_at,
            version_count=len(artifact.versions),
        )
