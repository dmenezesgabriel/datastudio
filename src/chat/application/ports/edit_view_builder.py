"""Port for applying one streamed edit onto a saved dashboard view.

An edit yields the same ephemeral events as a build (widget data, LLM view patches, SQL),
but they target *existing* element ids and must be layered onto the artifact's current
spec rather than compiled from scratch. Applying json-render patches is an infrastructure
concern, so the edit use case depends only on this port.
"""

from collections.abc import Sequence
from typing import Protocol

from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.stream_event import ChatStreamEvent


class EditViewBuilder(Protocol):
    """Layers one edit's stream events onto an existing dashboard tree.

    Returns the prior spec unchanged when the edit produced no patches, so the caller
    can tell a no-op edit from a real one (and skip recording an identical version).

    Example:
        edited = builder.build(prior_spec, events)  # prior_spec with the edit applied
    """

    def build(self, prior_spec: RenderTree, events: Sequence[ChatStreamEvent]) -> RenderTree:
        """Return ``prior_spec`` with the edit's patches applied (or unchanged if none)."""
        ...
