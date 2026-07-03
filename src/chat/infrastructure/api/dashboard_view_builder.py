"""Builds a persistable dashboard RenderTree from one turn's stream events.

Mirrors what the streaming ``SpecStreamSerializer`` puts on the wire, but as a stored
snapshot: it compiles the LLM's view patches + narrative + per-widget SQL into the
element tree (reusing ``compile_view_tree``) and attaches each widget's ``{columns, rows}``
state, so a reopened thread re-renders its charts/tables — not just its text.
"""

from collections.abc import Sequence

from chat.application.ports.turn_view_builder import TurnViewBuilder
from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    SqlReady,
    ViewPatchLine,
    WidgetDataReady,
)
from chat.infrastructure.api.spec_stream import state_value
from chat.infrastructure.graph.view.render_tree_builder import compile_view_tree, narrative_tree


class DashboardViewBuilder(TurnViewBuilder):
    """Compiles a turn's events into a full RenderTree (elements + widget state).

    Example:
        view = DashboardViewBuilder().build(events)
        view.state  # {"widget-0": {"columns": [...], "rows": [...]}}
    """

    def build(self, events: Sequence[ChatStreamEvent]) -> RenderTree:
        """Assemble the persistable dashboard tree from one answered question's events."""
        narrative = _last_narrative(events)
        view_lines = _view_patch_lines(events)
        sql = _combined_sql(events)
        state = {
            e.widget_id: state_value(e.result) for e in events if isinstance(e, WidgetDataReady)
        }
        if not view_lines:
            return narrative_tree(narrative)  # narrative-only answer (no dashboard)
        tree = compile_view_tree(narrative, view_lines, sql)
        return tree.model_copy(update={"state": state})


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


def _combined_sql(events: Sequence[ChatStreamEvent]) -> str:
    """Join the per-widget SQL into one disclosure block (empty when none ran)."""
    return "\n\n".join(e.sql_query for e in events if isinstance(e, SqlReady) and e.sql_query)
