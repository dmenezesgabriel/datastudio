"""Artifact aggregate: a saved dashboard with an append-only revision history."""

from chat.domain.value_objects.artifact_version import ArtifactVersion
from chat.domain.value_objects.render_tree import RenderTree
from shared.domain.errors import InvariantViolationError


class Artifact:
    """A promoted dashboard: an identified, owner-scoped, editable json-render spec.

    Holds an append-only log of immutable ``versions`` and a ``current`` pointer into
    it. Editing appends a new version and advances the pointer to it; reverting moves
    the pointer to an earlier version **without dropping any** (so the user can step
    back and forward freely). ``owner_id`` is a foreign identifier into the identity
    context; the repository scopes reads by it so a caller only sees their own artifacts.

    Example:
        art = Artifact.create("a-1", "guest", "Revenue overview", spec, now)
        art.append_version(edited_spec, "make it a line chart", now)
        art.set_current(0)  # revert to the first version (non-destructive)
    """

    def __init__(
        self,
        artifact_id: str,
        owner_id: str,
        title: str,
        versions: list[ArtifactVersion],
        current: int,
        source_conversation_id: str | None = None,
    ) -> None:
        """Build an artifact from its id, owner, title, version log, and active pointer."""
        self.artifact_id = artifact_id
        self.owner_id = owner_id
        self.title = title
        self.versions = versions
        self.current = current
        self.source_conversation_id = source_conversation_id

    @classmethod
    def create(
        cls,
        artifact_id: str,
        owner_id: str,
        title: str,
        spec: RenderTree,
        created_at: float,
        source_conversation_id: str | None = None,
    ) -> "Artifact":
        """Start an artifact from its first saved dashboard spec (version 0)."""
        initial = ArtifactVersion(spec=spec, instruction=None, created_at=created_at)
        return cls(artifact_id, owner_id, title, [initial], 0, source_conversation_id)

    @property
    def current_spec(self) -> RenderTree:
        """The spec of the active version — what consumers render as "the" dashboard."""
        return self.versions[self.current].spec

    @property
    def updated_at(self) -> float:
        """Last-modified time: the timestamp of the most recently appended version."""
        return self.versions[-1].created_at

    def append_version(self, spec: RenderTree, instruction: str, created_at: float) -> None:
        """Record an edit as a new tip version and make it current.

        ``instruction`` is the edit request that produced ``spec`` — it becomes the
        version's change description in the history.
        """
        version = ArtifactVersion(spec=spec, instruction=instruction, created_at=created_at)
        self.versions.append(version)
        self.current = len(self.versions) - 1

    def set_current(self, index: int) -> None:
        """Point the artifact at version ``index`` (revert / step back-forward).

        Non-destructive: no versions are removed, so a later index remains reachable.
        Raises ``InvariantViolationError`` when ``index`` is outside the version log.
        """
        if not 0 <= index < len(self.versions):
            raise InvariantViolationError(
                f"version index {index} out of range [0, {len(self.versions)})"
            )
        self.current = index
