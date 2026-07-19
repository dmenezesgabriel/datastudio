"""Use case: edit a saved dashboard via chat and record the result as a new version."""

import time

from chat.application.ports.artifact_repository import ArtifactRepository
from chat.application.ports.dashboard_view_builder import DashboardViewBuilder
from chat.application.ports.edit_dashboard_port import EditDashboardPort
from chat.domain.errors import ArtifactNotFoundError
from chat.domain.value_objects.stream_event import ChatStreamEvent, ProgressStep, TypedChatStream


class EditArtifact:
    """Streams a conversational edit of an artifact, then appends the result as a version.

    Loads the artifact's current spec, drives the edit engine over it (forwarding every
    event so the client updates live), then layers the edit's patches onto that spec and
    records it as a new version — the instruction becomes the version's change description.
    A no-op edit (no patches produced) records nothing. Dependencies are injected so the
    use case stays infra-free, mirroring ``StreamMessage``.

    Example:
        use_case = EditArtifact(repository, engine, view_builder)
        async for event in use_case.execute("guest", "a-1", "make it a line chart"):
            ...
    """

    def __init__(
        self,
        repository: ArtifactRepository,
        engine: EditDashboardPort,
        view_builder: DashboardViewBuilder,
    ) -> None:
        """Wire the artifact repository, the edit engine, and the dashboard view builder."""
        self._repository = repository
        self._engine = engine
        self._view_builder = view_builder

    async def execute(self, owner_id: str, artifact_id: str, instruction: str) -> TypedChatStream:
        """Stream the edit for the caller's artifact, then persist it as a new version.

        Scoped to ``owner_id``: a missing or foreign artifact raises before any work, so a
        caller can never edit another user's dashboard. The current spec seeds the engine
        as the whole edit state (no conversation memory needed).
        """
        artifact = self._repository.get(artifact_id, owner_id)
        if artifact is None:
            raise ArtifactNotFoundError(f"artifact {artifact_id!r} not found")
        prior_spec = artifact.current_spec
        events: list[ChatStreamEvent] = []
        async for event in self._engine.edit(prior_spec, instruction):
            if not isinstance(event, ProgressStep):
                events.append(event)  # keep the payload; progress is transient chrome
            yield event
        edited = self._view_builder.apply_edit(prior_spec, events)
        if edited is not prior_spec:  # only version a real change
            artifact.append_version(edited, instruction, time.time())
            self._repository.save(artifact)
