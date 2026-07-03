"""Port for compiling one streamed answer into a persistable dashboard view.

The streamed events (widget data, LLM view patches, SQL, narrative) are ephemeral; to
reopen a past thread and re-render its charts/tables — not just its text — the assistant
turn must be persisted as a full ``RenderTree`` (elements + state). Building that tree
means applying json-render patches, an infrastructure concern, so the use case depends
only on this port.
"""

from collections.abc import Sequence
from typing import Protocol

from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.stream_event import ChatStreamEvent


class TurnViewBuilder(Protocol):
    """Compiles one turn's stream events into a full renderable dashboard tree.

    Example:
        view = builder.build(events)  # RenderTree with elements + widget state
    """

    def build(self, events: Sequence[ChatStreamEvent]) -> RenderTree:
        """Return the persistable dashboard view for one answered question."""
        ...
