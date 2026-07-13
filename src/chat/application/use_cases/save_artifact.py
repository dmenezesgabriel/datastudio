"""Use case: promote a rendered dashboard into a saved, versioned artifact."""

import time
from uuid import uuid4

from chat.application.ports.artifact_repository import ArtifactRepository
from chat.domain.entities.artifact import Artifact
from chat.domain.value_objects.render_tree import RenderTree


class SaveArtifact:
    """Creates a new artifact from a dashboard spec and returns its id.

    The spec is supplied by the caller (the client already holds the tree it
    rendered), so saving reads nothing back from the originating conversation.

    Example:
        artifact_id = SaveArtifact(repository).execute("guest", "Revenue overview", spec)
    """

    def __init__(self, repository: ArtifactRepository) -> None:
        """Wire the artifact repository."""
        self._repository = repository

    def execute(
        self,
        owner_id: str,
        title: str,
        spec: RenderTree,
        source_conversation_id: str | None = None,
    ) -> str:
        """Mint an id, persist the artifact at version 0, and return the id."""
        artifact_id = uuid4().hex
        artifact = Artifact.create(
            artifact_id, owner_id, title, spec, time.time(), source_conversation_id
        )
        self._repository.save(artifact)
        return artifact_id
