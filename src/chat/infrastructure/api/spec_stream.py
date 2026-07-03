"""Translate engine stream events into a json-render SpecStream.

SpecStream is json-render's documented streaming wire format: a newline-delimited
body where each line is one RFC-6902 JSON-Patch op. Per json-render's own guidance
("stream /elements and /state patches interleaved"), this serializer streams each
widget's rows as a backend-authored ``/state/<id>`` patch — so the data reaches the
chart via ``$state`` **without ever passing through the view-authoring model** — and
passes the LLM's namespaced ``/elements`` patches through verbatim. The narrative and
per-widget SQL are deterministic elements owned here.
See https://json-render.dev/docs/streaming for the format.
"""

import json
from datetime import date, datetime, time
from decimal import Decimal

from chat.domain.value_objects.render_tree import RenderElement
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    ProgressStep,
    ViewPatchLine,
    WidgetDataReady,
)
from chat.infrastructure.graph.view.render_tree_builder import build_markdown_element
from shared.domain.value_objects.query_result import QueryResult

# The narrative answer lives under a fixed id so the final summary replaces any earlier
# text in place (no add/remove flicker).
_NARRATIVE_ID = "narrative"

# Cap rows put on the wire so a large detail result can't bloat the stream.
_MAX_STREAM_ROWS = 500


def _json_default(value: object) -> object:
    """Coerce DB cell types ``json.dumps`` can't encode to JSON-native ones.

    DuckDB returns ``date``/``datetime``/``Decimal`` objects for temporal and exact-
    numeric columns; the ``$state`` wire is JSON, so temporals become ISO-8601 strings
    and decimals become floats (the chart/table bindings read them as-is). Without this
    a single date/timestamp/Decimal cell in a widget's rows would raise TypeError and
    sink the whole dashboard stream.
    """
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _patch_line(op: str, path: str, value: object) -> str:
    """Serialize a single RFC-6902 patch op to a compact JSON line."""
    return json.dumps(
        {"op": op, "path": path, "value": value}, ensure_ascii=False, default=_json_default
    )


def _state_rows(result: QueryResult) -> list[dict[str, object]]:
    """Capped array-of-row-objects the chart/table $state bindings resolve against."""
    return [dict(zip(result.columns, row, strict=True)) for row in result.rows[:_MAX_STREAM_ROWS]]


def state_value(result: QueryResult) -> dict[str, object]:
    """The ``{columns, rows}`` object a widget's ``$state`` bindings read (row-capped).

    Shared by the streaming serializer and the persisted-dashboard builder so the wire
    and the stored snapshot shape a widget's data identically.
    """
    return {"columns": result.columns, "rows": _state_rows(result)}


class SpecStreamSerializer:
    """Stateful translator from ``ChatStreamEvent`` to SpecStream patch lines.

    One instance per answered question. It owns the deterministic narrative + SQL
    elements and the per-widget ``/state`` data patches, and forwards the LLM's
    visualization patches unchanged.

    Example:
        serializer = SpecStreamSerializer()
        for line in serializer.lines_for(WidgetDataReady("widget-0", result)):
            await response.write(line + newline)
    """

    def __init__(self) -> None:
        """Start with an uninitialized spec, no narrative, and no progress steps yet."""
        self._root_initialized = False
        self._narrative_added = False
        self._progress_initialized = False
        self._progress_orders: dict[str, int] = {}

    def lines_for(self, event: ChatStreamEvent) -> list[str]:
        """Return the patch lines for one event, advancing internal state."""
        if isinstance(event, ProgressStep):
            return self._progress_lines(event)
        if isinstance(event, NarrativeReady):
            return self._narrative_lines(event.text)
        if isinstance(event, WidgetDataReady):
            return [
                _patch_line("add", f"/state/{event.widget_id}", self._state_value(event.result))
            ]
        if isinstance(event, ViewPatchLine):
            return self._root_init_lines() + [event.line]
        return self._sql_lines(event.widget_id, event.sql_query)  # SqlReady (union exhausted)

    def _progress_lines(self, step: ProgressStep) -> list[str]:
        """Add a checklist step under ``/state/progress`` on first sight; replace status after.

        Progress rides a reserved ``/state/progress`` key (never ``/elements``) so the
        live checklist stays out of the answer tree. It lives under ``/state`` — not a
        top-level ``/progress`` — because the json-render client only applies ``/state``
        and ``/elements`` patches; unknown top-level paths are dropped. The key can't
        collide with a widget's ``/state/<widget_id>`` data (ids are ``widget-N``). Each
        step carries an ``order`` (first-seen index) so the client renders pipeline order.
        """
        lines = self._progress_init_lines()
        if step.step_id in self._progress_orders:
            path = f"/state/progress/{step.step_id}/status"
            return lines + [_patch_line("replace", path, step.status)]
        order = len(self._progress_orders)
        self._progress_orders[step.step_id] = order
        value = {
            "label": step.label,
            "status": step.status,
            "parentId": step.parent_id,
            "order": order,
        }
        return lines + [_patch_line("add", f"/state/progress/{step.step_id}", value)]

    def _progress_init_lines(self) -> list[str]:
        """Emit the empty ``/state/progress`` map exactly once (no-op afterwards)."""
        if self._progress_initialized:
            return []
        self._progress_initialized = True
        return [_patch_line("add", "/state/progress", {})]

    def _state_value(self, result: QueryResult) -> dict[str, object]:
        """The ``{columns, rows}`` object a widget's $state bindings read."""
        return state_value(result)

    def _narrative_lines(self, text: str) -> list[str]:
        """Add the narrative element on first use; replace its text thereafter."""
        if self._narrative_added:
            return [_patch_line("replace", f"/elements/{_NARRATIVE_ID}/props/text", text)]
        lines = self._root_init_lines()
        lines += self._add_element_lines(_NARRATIVE_ID, build_markdown_element(text))
        self._narrative_added = True
        return lines

    def _sql_lines(self, widget_id: str, sql_query: str) -> list[str]:
        """Emit a per-widget SQL-disclosure Markdown element (skipped when empty)."""
        if not sql_query:
            return []
        lines = self._root_init_lines()
        lines += self._add_element_lines(
            f"{widget_id}-sql", build_markdown_element(f"```sql\n{sql_query}\n```")
        )
        return lines

    def _root_init_lines(self) -> list[str]:
        """Emit the root id + empty root Stack exactly once (no-op afterwards)."""
        if self._root_initialized:
            return []
        self._root_initialized = True
        root = RenderElement(type="Stack", props={}, children=[])
        return [
            _patch_line("add", "/root", "root"),
            _patch_line("add", "/elements/root", root.model_dump()),
        ]

    def _add_element_lines(self, element_id: str, element: RenderElement) -> list[str]:
        """Add one element and reference it from the root Stack's children."""
        return [
            _patch_line("add", f"/elements/{element_id}", element.model_dump()),
            _patch_line("add", "/elements/root/children/-", element_id),
        ]
