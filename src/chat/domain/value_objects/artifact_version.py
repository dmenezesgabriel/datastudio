"""Immutable value object: one saved snapshot in an artifact's revision history."""

from dataclasses import dataclass

from chat.domain.value_objects.render_tree import RenderTree


@dataclass(frozen=True)
class ArtifactVersion:
    """A single point-in-time snapshot of an artifact's dashboard spec.

    ``instruction`` is the edit request that produced this version (the change
    description shown in the history), or ``None`` for the initial saved version.
    Full-spec snapshots (not patch deltas) keep navigation O(1) and revert trivial.

    Example:
        ArtifactVersion(spec=tree, instruction="make the revenue chart a line chart",
                        created_at=1751500000.0)
    """

    spec: RenderTree
    instruction: str | None
    created_at: float
