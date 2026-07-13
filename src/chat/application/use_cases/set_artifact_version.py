"""Use case: move an artifact's active pointer (revert / step back-forward)."""

from chat.application.ports.artifact_repository import ArtifactRepository
from chat.domain.entities.artifact import Artifact
from chat.domain.errors import ArtifactNotFoundError


class SetArtifactVersion:
    """Points an artifact at an earlier (or later) version without dropping any.

    Backs revert and history navigation: the version log is append-only, so this
    only moves the ``current`` pointer. Returns the artifact so the caller can
    surface the now-active spec.

    Example:
        artifact = SetArtifactVersion(repository).execute("guest", "a-1", 0)
        artifact.current_spec  # the reverted-to dashboard
    """

    def __init__(self, repository: ArtifactRepository) -> None:
        """Wire the artifact repository."""
        self._repository = repository

    def execute(self, owner_id: str, artifact_id: str, index: int) -> Artifact:
        """Load the caller's artifact (or 404), point it at ``index``, and persist."""
        artifact = self._repository.get(artifact_id, owner_id)
        if artifact is None:
            raise ArtifactNotFoundError(f"artifact {artifact_id!r} not found")
        artifact.set_current(index)
        self._repository.save(artifact)
        return artifact
