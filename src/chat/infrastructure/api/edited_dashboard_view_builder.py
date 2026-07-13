"""Applies one edit's stream events onto an artifact's current dashboard spec.

The edit counterpart of ``DashboardViewBuilder``: rather than compiling a fresh tree, it
maps the edit events back to the same wire patches the streaming serializer puts on the
client (view patches verbatim, each widget's rows as a ``/state`` patch, each rebuilt
widget's SQL as a frame ``/props/sql`` replace) and layers them onto the prior spec — so
the persisted result matches exactly what the client rendered live.
"""

from collections.abc import Sequence

from chat.application.ports.edit_view_builder import EditViewBuilder
from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    SqlReady,
    ViewPatchLine,
    WidgetDataReady,
)
from chat.infrastructure.api.spec_stream import patch_line, state_value
from chat.infrastructure.graph.view.render_tree_builder import apply_patch_lines


class EditedDashboardViewBuilder(EditViewBuilder):
    """Layers an edit's patches onto the prior spec, or returns it unchanged if none.

    Example:
        edited = EditedDashboardViewBuilder().build(prior_spec, events)
    """

    def build(self, prior_spec: RenderTree, events: Sequence[ChatStreamEvent]) -> RenderTree:
        """Apply the edit's patch lines to ``prior_spec`` (unchanged when the edit is a no-op)."""
        lines = _edit_patch_lines(events)
        if not lines:
            return prior_spec  # nothing changed — caller skips recording an identical version
        return apply_patch_lines(prior_spec, lines)


def _edit_patch_lines(events: Sequence[ChatStreamEvent]) -> list[str]:
    """Map edit events to the persistence patch lines (view, per-widget data, SQL).

    The narrative is intentionally omitted: an edit changes widgets, not the dashboard's
    summary, so the artifact's own narrative element is left intact.
    """
    lines: list[str] = []
    for event in events:
        if isinstance(event, ViewPatchLine):
            lines.append(event.line)
        elif isinstance(event, WidgetDataReady):
            lines.append(patch_line("add", f"/state/{event.widget_id}", state_value(event.result)))
        elif isinstance(event, SqlReady) and event.sql:
            lines.append(
                patch_line("replace", f"/elements/{event.widget_id}-frame/props/sql", event.sql)
            )
    return lines
