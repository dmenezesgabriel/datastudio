"""Compiles a turn's stream events into a persistable dashboard RenderTree.

The single adapter behind ``DashboardViewBuilder``. ``build`` mirrors what the streaming
``SpecStreamSerializer`` puts on the wire, but as a stored snapshot: it compiles the LLM's
view patches + narrative + per-widget SQL into the element tree (reusing ``compile_render_tree``)
and attaches each widget's ``{columns, rows}`` state, so a reopened thread re-renders its
charts/tables — not just its text. ``apply_edit`` instead maps an edit's events back to the
same wire patches and layers them onto the artifact's current spec, so the persisted result
matches exactly what the client rendered live.
"""

from collections.abc import Sequence

from chat.application.ports.dashboard_view_builder import DashboardViewBuilder
from chat.domain.value_objects.dashboard_layout import frame_id
from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    SqlReady,
    ViewPatchLine,
    WidgetDataReady,
)
from chat.infrastructure.api.spec_stream import patch_line, state_value
from chat.infrastructure.graph.view.render_tree_builder import (
    apply_patch_lines,
    compile_render_tree,
    narrative_tree,
)


class SpecStreamDashboardViewBuilder(DashboardViewBuilder):
    """Builds/edits a persistable RenderTree from SpecStream-shaped stream events.

    Example:
        view = SpecStreamDashboardViewBuilder().build(events)
        view.state  # {"widget-0": {"columns": [...], "rows": [...]}}
    """

    def build(self, events: Sequence[ChatStreamEvent]) -> RenderTree:
        """Assemble the persistable dashboard tree from one answered question's events."""
        narrative = _last_narrative(events)
        patch_lines = _view_patch_lines(events)
        sql_by_widget = _sql_by_widget(events)
        state = {
            e.widget_id: state_value(e.result) for e in events if isinstance(e, WidgetDataReady)
        }
        if not patch_lines:
            return narrative_tree(narrative)  # narrative-only answer (no dashboard)
        tree = compile_render_tree(narrative, patch_lines, sql_by_widget)
        return tree.model_copy(update={"state": state})

    def apply_edit(self, prior_spec: RenderTree, events: Sequence[ChatStreamEvent]) -> RenderTree:
        """Apply the edit's patch lines to ``prior_spec`` (unchanged when the edit is a no-op)."""
        lines = _edit_patch_lines(events)
        if not lines:
            return prior_spec  # nothing changed — caller skips recording an identical version
        return apply_patch_lines(prior_spec, lines)


def _view_patch_lines(events: Sequence[ChatStreamEvent]) -> list[str]:
    r"""Flatten each ViewPatchLine into individual RFC-6902 patch lines.

    A single ``ViewPatchLine`` may carry several newline-joined patches (e.g. add the
    widget element, then append it to the root's children). On the wire the client
    splits them on ``\n``; the compiler applies one patch per line, so split here too —
    otherwise a multi-patch line fails to parse and the widget is silently dropped.
    """
    return [
        part
        for event in events
        if isinstance(event, ViewPatchLine)
        for part in event.line.split("\n")
        if part.strip()
    ]


def _last_narrative(events: Sequence[ChatStreamEvent]) -> str:
    """The turn's final summary text (empty when the stream produced none)."""
    texts = [e.text for e in events if isinstance(e, NarrativeReady)]
    return texts[-1] if texts else ""


def _sql_by_widget(events: Sequence[ChatStreamEvent]) -> dict[str, str]:
    """Map each widget id to the SQL that produced it, for its frame's disclosure toggle."""
    return {e.widget_id: e.sql for e in events if isinstance(e, SqlReady) and e.sql}


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
                patch_line("replace", f"/elements/{frame_id(event.widget_id)}/props/sql", event.sql)
            )
    return lines
