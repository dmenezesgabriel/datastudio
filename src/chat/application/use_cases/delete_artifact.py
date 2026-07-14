"""Use case: delete a saved artifact owned by the caller."""

from chat.application.ports.artifact_repository import ArtifactRepository


class DeleteArtifact:
    """Removes one of the caller's artifacts (a no-op for an absent or foreign id).

    Keeps the write boundary uniform: like save and revert, deletion flows through a use
    case rather than the router touching the repository directly. Owner scoping lives in
    the repository, so a caller can never delete another user's artifact.

    Example:
        DeleteArtifact(repository).execute("guest", "a-1")
    """

    def __init__(self, repository: ArtifactRepository) -> None:
        """Wire the artifact repository."""
        self._repository = repository

    def execute(self, owner_id: str, artifact_id: str) -> None:
        """Delete the caller's artifact; ignore ids that are absent or owned by another."""
        self._repository.delete(artifact_id, owner_id)
