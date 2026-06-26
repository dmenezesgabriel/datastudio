"""Pure assembly of a json-render tree from a ViewSpec + QueryResult.

No LLM and no I/O: the recommend_view node decides *intent* (a ``ViewSpec``) and
this module injects the real data deterministically. Charts/KPIs that reference a
column absent from the result are dropped rather than raising, so a slightly wrong
recommendation degrades gracefully instead of failing the request.

The emitted component ``type`` names and prop shapes must stay in sync with the
frontend Zod catalogue (``frontend/src/catalog.ts``).
"""

from collections.abc import Callable, Sequence
from decimal import Decimal

from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.view_spec import ChartSpec, KpiSpec, ViewSpec
from shared.domain.value_objects.query_result import QueryResult


def column_index(query_result: QueryResult, name: str) -> int | None:
    """Return the position of ``name`` in the result columns, or None if absent."""
    try:
        return query_result.columns.index(name)
    except ValueError:
        return None


def build_markdown_element(text: str) -> RenderElement:
    """Build the narrative Markdown element."""
    props: dict[str, object] = {"text": text}
    return RenderElement(type="Markdown", props=props, children=[])


def build_kpi_element(kpi: KpiSpec, query_result: QueryResult) -> RenderElement | None:
    """Build a KPI element from a single-row result, or None when not applicable.

    A KPI is a single, unambiguous headline figure, so it is only emitted for a
    one-row result. On multi-row results "the value" would just be an arbitrary
    first row — e.g. a dashboard UNION-ALL query that would otherwise label the
    first month's revenue as the grand total.
    """
    index = column_index(query_result, kpi.value_column)
    if index is None or query_result.row_count != 1:
        return None
    value = _format_value(query_result.rows[0][index])
    props: dict[str, object] = {"label": kpi.label, "value": value}
    return RenderElement(type="KpiStat", props=props, children=[])


def build_chart_element(chart: ChartSpec, query_result: QueryResult) -> RenderElement | None:
    """Build a Chart.js element, or None if a column is missing or nothing is plottable."""
    label_index = column_index(query_result, chart.label_column)
    value_indexes = _resolve_indexes(query_result, chart.value_columns)
    if label_index is None or value_indexes is None:
        return None
    # Drop rows without a label: they can't be plotted and otherwise surface as
    # "None" categories (e.g. heterogeneous UNION-ALL dashboard result sets).
    rows = [row for row in query_result.rows if row[label_index] is not None]
    if not rows:
        return None
    datasets = [
        _build_dataset(column, index, rows)
        for column, index in zip(chart.value_columns, value_indexes, strict=True)
    ]
    props: dict[str, object] = {
        "kind": chart.kind,
        "title": chart.title,
        "labels": [str(row[label_index]) for row in rows],
        "datasets": datasets,
    }
    return RenderElement(type="ChartJs", props=props, children=[])


def build_table_element(query_result: QueryResult) -> RenderElement:
    """Build the full data table element from the result set."""
    props: dict[str, object] = {
        "columns": query_result.columns,
        "rows": [list(row) for row in query_result.rows],
    }
    return RenderElement(type="DataTable", props=props, children=[])


def narrative_tree(narrative: str) -> RenderTree:
    """Build a tree with only the narrative answer (used on the SQL-failure path)."""
    elements = {
        "narrative": build_markdown_element(narrative),
        "root": RenderElement(type="Stack", props={}, children=["narrative"]),
    }
    return RenderTree(root="root", elements=elements)


def assemble_render_tree(
    view_spec: ViewSpec, query_result: QueryResult, narrative: str
) -> RenderTree:
    """Assemble the full render tree: narrative, valid KPIs/charts, optional table.

    Example:
        tree = assemble_render_tree(spec, result, "There are 42 orders.")
    """
    elements: dict[str, RenderElement] = {"narrative": build_markdown_element(narrative)}
    child_ids = ["narrative"]
    _append_elements(elements, child_ids, view_spec.kpis, "kpi", build_kpi_element, query_result)
    _append_elements(
        elements, child_ids, view_spec.charts, "chart", build_chart_element, query_result
    )
    if view_spec.show_table:
        elements["table"] = build_table_element(query_result)
        child_ids.append("table")
    elements["root"] = RenderElement(type="Stack", props={}, children=child_ids)
    return RenderTree(root="root", elements=elements)


def _resolve_indexes(query_result: QueryResult, columns: list[str]) -> list[int] | None:
    """Resolve every column name to an index, or None if any is missing."""
    indexes: list[int] = []
    for name in columns:
        index = column_index(query_result, name)
        if index is None:
            return None
        indexes.append(index)
    return indexes


def _build_dataset(column: str, index: int, rows: list[tuple[object, ...]]) -> dict[str, object]:
    """Build one Chart.js dataset (label + column values) from the plottable rows."""
    return {"label": column, "data": [row[index] for row in rows]}


def _format_value(value: object) -> str:
    """Format a KPI value: thousands separators for numbers, str() otherwise."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, Decimal | float):
        return f"{value:,.2f}"
    return str(value)


def _append_elements[Spec](
    elements: dict[str, RenderElement],
    child_ids: list[str],
    specs: Sequence[Spec],
    prefix: str,
    build: Callable[[Spec, QueryResult], RenderElement | None],
    query_result: QueryResult,
) -> None:
    """Append each non-None built element under ``prefix-<index>`` ids (drops invalid)."""
    for index, spec in enumerate(specs):
        element = build(spec, query_result)
        if element is not None:
            key = f"{prefix}-{index}"
            elements[key] = element
            child_ids.append(key)
