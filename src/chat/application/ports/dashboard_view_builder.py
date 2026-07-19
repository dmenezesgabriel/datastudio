"""Port for turning a turn's stream events into a persistable dashboard view.

The streamed events (widget data, LLM view patches, SQL, narrative) are ephemeral; to
reopen a past thread and re-render its charts/tables — not just its text — the dashboard
must be persisted as a full ``RenderTree`` (elements + state). Building or editing that
tree means applying json-render patches, an infrastructure concern, so the use cases
depend only on this port.

``build`` compiles a fresh answer from scratch; ``apply_edit`` layers an edit's patches
onto an artifact's *existing* spec (its patches target existing element ids). Both halves
are the same concept — compile stream events into a persisted view — so they live behind
one port, fulfilled by one adapter.
"""

from collections.abc import Sequence
from typing import Protocol

from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.stream_event import ChatStreamEvent


class DashboardViewBuilder(Protocol):
    """Compiles a turn's stream events into a persistable dashboard tree.

    Example:
        view = builder.build(events)                      # a fresh answered question
        edited = builder.apply_edit(prior_spec, events)   # an edit layered on a saved spec
    """

    def build(self, events: Sequence[ChatStreamEvent]) -> RenderTree:
        """Return the persistable dashboard view for one answered question."""
        ...

    def apply_edit(self, prior_spec: RenderTree, events: Sequence[ChatStreamEvent]) -> RenderTree:
        """Return ``prior_spec`` with the edit's patches applied.

        Returns ``prior_spec`` unchanged when the edit produced no patches, so the caller
        can tell a no-op edit from a real one (and skip recording an identical version).
        """
        ...
