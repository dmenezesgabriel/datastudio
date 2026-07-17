"""Deterministic host-side shape guard over an authored widget view.

json-render's catalog validates that an element's ``type`` and ``props`` are well-formed, but
not that the component *fits the data shape* — a bar chart bound to a single row is schema-valid
yet wrong. This module enforces that domain invariant on the model's patch lines before they are
namespaced, the same host-authority stage that already rewrites region and ``$state`` paths (see
``generate_widget_view.namespace_widget_patches``). It mirrors the rules the eval's
``ChartFitCheck`` and ``viz_rubric`` assert, so the app produces what the suite grades as correct:

- a SINGLE-row result is a headline answer, never a chart → a ``KpiStat`` (metric role) or a
  one-row ``DataTable`` (analysis role);
- a pie with more than five slices is unreadable → downgrade it to a bar;
- a ``KpiStat`` cannot summarise many rows → show them as a ``DataTable``.

Only the unambiguous, data-determined cases are touched; a multi-row chart-vs-table choice stays
the worker's judgement, and a composite (multi-element) view is left untouched.
"""

import json
from decimal import Decimal
from typing import cast

from chat.domain.value_objects.widget import WidgetRole, WidgetViewHint
from chat.infrastructure.graph.spec_patch import parse_patch
from shared.domain.value_objects.query_result import QueryResult

# The catalog's data-binding contract (see catalog_prompt.generated.txt): a chart/KPI reads the
# result rows, a table the whole result. Kept local so this guard stays decoupled from the nodes.
_DATA_ROOT = "/result"
_ROWS_BINDING = "/result/rows"
_MAX_PIE_SLICES = 5


def coerce_view_to_shape(
    lines: list[str],
    role: WidgetRole,
    query_result: QueryResult,
    view_hint: WidgetViewHint | None = None,
) -> list[str]:
    """Rewrite the authored leaf so it fits the result shape; pass every other line through.

    A non-null ``view_hint`` means the user explicitly chose the presentation, so the guard
    defers — the user's stated wish wins (mirrors ``_VIEW_HINT_GUIDANCE``); the guard only ever
    overrides the model's *automatic* data-shape choice.

    Example:
        coerce_view_to_shape(chart_lines, "analysis", one_row_result)  # → one-row DataTable
    """
    if view_hint is not None:
        return lines
    leaf = _sole_leaf(lines)
    if leaf is None:
        return lines
    index, patch = leaf
    fitted = _fit_element(cast(dict[str, object], patch["value"]), role, query_result)
    if fitted is None:
        return lines
    return [*lines[:index], json.dumps({**patch, "value": fitted}), *lines[index + 1 :]]


def _sole_leaf(lines: list[str]) -> tuple[int, dict[str, object]] | None:
    """The single element-defining patch (``/elements/<id>`` add with a typed value), or None.

    None when zero or several elements were authored, so a composite view is left untouched —
    the guard only rewrites the one-element case whose data shape it can reason about.
    """
    found: tuple[int, dict[str, object]] | None = None
    for index, line in enumerate(lines):
        patch = parse_patch(line)
        if patch is None or not _defines_element(patch):
            continue
        if found is not None:
            return None
        found = (index, patch)
    return found


def _defines_element(patch: dict[str, object]) -> bool:
    """True when a patch adds a typed element (not a ``.../children/-`` reference append)."""
    path, value = patch.get("path"), patch.get("value")
    return (
        isinstance(path, str)
        and path.startswith("/elements/")
        and not path.endswith("/children/-")
        and isinstance(value, dict)
        and "type" in value
    )


def _fit_element(
    element: dict[str, object], role: WidgetRole, query_result: QueryResult
) -> dict[str, object] | None:
    """A shape-corrected replacement for one element, or None when it already fits the data."""
    element_type = element.get("type")
    if element_type == "KpiStat" and query_result.row_count > 1:
        return _data_table()
    if element_type != "ChartJs":
        return None
    if query_result.row_count == 1:
        return _single_row_replacement(role, query_result)
    if _is_oversized_pie(element, query_result.row_count):
        return _as_bar(element)
    return None


def _single_row_replacement(role: WidgetRole, query_result: QueryResult) -> dict[str, object]:
    """A KpiStat (metric headline number) or a one-row DataTable for a charted single row."""
    value_column = _first_numeric_column(query_result)
    if role == "metric" and value_column is not None:
        return _kpi_stat(value_column)
    return _data_table()


def _is_oversized_pie(element: dict[str, object], rows: int) -> bool:
    """True when the chart is a pie bound to more slices than are readable."""
    props = element.get("props")
    if not isinstance(props, dict):
        return False
    return cast(dict[str, object], props).get("kind") == "pie" and rows > _MAX_PIE_SLICES


def _as_bar(element: dict[str, object]) -> dict[str, object]:
    """The same chart re-kinded as a bar (its labels/series/binding are preserved)."""
    props = cast(dict[str, object], element["props"])
    return {**element, "props": {**props, "kind": "bar"}}


def _kpi_stat(value_column: str) -> dict[str, object]:
    """A KpiStat showing one numeric column of the single result row."""
    return {
        "type": "KpiStat",
        "props": {
            "label": value_column,
            "valueColumn": value_column,
            "data": {"$state": _ROWS_BINDING},
        },
        "children": [],
    }


def _data_table() -> dict[str, object]:
    """A DataTable bound to the whole result — the safe view for any shape."""
    return {"type": "DataTable", "props": {"data": {"$state": _DATA_ROOT}}, "children": []}


def _first_numeric_column(query_result: QueryResult) -> str | None:
    """Name of the first column whose value in the single row is numeric, or None."""
    if not query_result.rows:
        return None
    row = query_result.rows[0]
    for index, name in enumerate(query_result.columns):
        value = row[index]
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float | Decimal):
            return name
    return None
