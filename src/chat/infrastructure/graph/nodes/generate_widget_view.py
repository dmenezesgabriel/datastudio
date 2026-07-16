"""Authoring one dashboard widget's view as a namespaced json-render SpecStream.

The LLM authors a single visualization (chart/KPI/table) for a widget, binding its
data to ``{"$state":"/result/rows"}`` and seeing only the result *schema* (never the
values). Because widgets are built in parallel and share one root, this module then
deterministically **namespaces** the LLM's element ids and ``$state`` paths to the
widget (e.g. ``/elements/widget-0-chart``, ``$state:"/widget-0/rows"``) so concurrent
widgets never collide. Invalid output falls back to a DataTable.
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from chat.domain.value_objects.widget import WidgetRole, WidgetViewHint
from chat.infrastructure.graph.response_content_extractor import (
    ResponseContentExtractor,
)
from chat.infrastructure.graph.spec_patch import parse_patch
from chat.infrastructure.graph.step_tags import step_tag
from shared.domain.value_objects.query_result import QueryResult

# Generated from the frontend json-render catalog by `npm run gen:prompt`, so the
# component vocabulary the model is told about stays in sync with what renders.
_CATALOG_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "catalog_prompt.generated.txt"
)

# The LLM authors against this neutral data root; per widget it is rewritten to /<id>.
_DATA_ROOT = "/result"
_RESERVED_EXACT = frozenset({"/root", "/elements/root"})
_RESERVED_PREFIXES = ("/elements/narrative", "/elements/sql")
_ALLOWED_OPS = frozenset({"add", "replace", "remove"})

# F-layout regions the backend seeds (see spec_stream / render_tree_builder): a widget's
# region is decided by its planner-declared role, not by the element the model authors —
# "metric" widgets go into the headline KPI band, everything else into the charts/tables grid.
_KPI_REGION = "kpi-row"
_GRID_REGION = "grid"
_ROOT_CHILDREN = "/elements/root/children/-"


def load_catalog_prompt() -> str:
    """Load the catalog-derived system prompt that constrains the view-authoring model."""
    return _CATALOG_PROMPT_PATH.read_text(encoding="utf-8")


def _is_reserved(path: str) -> bool:
    """True when a patch path targets a backend-owned element (narrative/root/sql)."""
    return path in _RESERVED_EXACT or path.startswith(_RESERVED_PREFIXES)


def keep_valid_patch_lines(text: str) -> list[str]:
    r"""Keep only well-formed, non-reserved JSON-Patch lines from raw model output.

    Example:
        keep_valid_patch_lines('{"op":"add","path":"/elements/x","value":1}\nthanks')
    """
    kept: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        patch = parse_patch(line)
        if patch is None:
            continue
        op, path = patch.get("op"), patch.get("path")
        if op in _ALLOWED_OPS and isinstance(path, str) and not _is_reserved(path):
            kept.append(line)
    return kept


def _rewrite_state(value: object, widget_id: str) -> object:
    """Recursively rewrite ``{"$state":"/result..."}`` bindings to the widget's path."""
    if isinstance(value, dict):
        typed = cast(dict[str, object], value)
        binding = typed.get("$state")
        if list(typed.keys()) == ["$state"] and isinstance(binding, str):
            if binding == _DATA_ROOT or binding.startswith(_DATA_ROOT + "/"):
                return {"$state": f"/{widget_id}{binding[len(_DATA_ROOT) :]}"}
        return {key: _rewrite_state(item, widget_id) for key, item in typed.items()}
    if isinstance(value, list):
        return [_rewrite_state(item, widget_id) for item in cast(list[object], value)]
    return value


def _region_for_role(role: WidgetRole) -> str:
    """Map a widget's planner-declared role to its F-layout region.

    Deterministic and independent of what the worker authored: a ``metric`` belongs in the
    headline KPI band, every ``analysis`` widget in the grid below it. This is the host's
    layout authority — the model only fills a component into the region we assign.
    """
    return _KPI_REGION if role == "metric" else _GRID_REGION


def namespace_widget_patches(lines: list[str], widget_id: str, role: WidgetRole) -> list[str]:
    """Namespace a widget's element ids/``$state`` and place it in its F-layout region.

    Prefixes element ids/child-refs with the widget id and rebinds ``$state`` so parallel
    widgets never collide, then routes the widget's root-child append into the ``kpi-row``
    band or the ``grid`` region (seeded by the serializer/compiler) per its declared role.
    """
    region = _region_for_role(role)
    out: list[str] = []
    for line in lines:
        patch = parse_patch(line)
        if patch is None or not isinstance(patch.get("path"), str):
            continue
        path = cast(str, patch["path"])
        if path == _ROOT_CHILDREN:
            child = patch.get("value")
            if isinstance(child, str):
                out.extend(_frame_patches(widget_id, f"{widget_id}-{child}", region))
            continue
        parts = path.split("/")
        if len(parts) < 3 or parts[1] != "elements" or parts[2] == "root":
            continue
        parts[2] = f"{widget_id}-{parts[2]}"
        value = _rewrite_state(patch.get("value"), widget_id)
        out.append(_patch(str(patch.get("op", "add")), "/".join(parts), value))
    return out


def _patch(op: str, path: str, value: object) -> str:
    return json.dumps({"op": op, "path": path, "value": value})


def _frame_patches(widget_id: str, child_id: str, region: str) -> list[str]:
    """Wrap a widget's leaf in a WidgetFrame (holds its SQL) placed in its F-layout region.

    The frame is backend-owned — the model authors only the leaf visualization. Wrapping
    every widget uniformly lets the serializer fill the SQL with one `/props/sql` patch (no
    per-widget special-casing); the ``sql`` prop starts empty and is set when SQL is ready.
    """
    frame_id = f"{widget_id}-frame"
    frame: dict[str, object] = {
        "type": "WidgetFrame",
        "props": {"sql": ""},
        "children": [child_id],
    }
    return [
        _patch("add", f"/elements/{frame_id}", frame),
        _patch("add", f"/elements/{region}/children/-", frame_id),
    ]


def _fallback_table_lines() -> list[str]:
    """Neutral DataTable bound to the data root, namespaced by the caller."""
    element: dict[str, object] = {
        "type": "DataTable",
        "props": {"data": {"$state": _DATA_ROOT}},
        "children": [],
    }
    return [
        _patch("add", "/elements/data-table", element),
        _patch("add", "/elements/root/children/-", "data-table"),
    ]


def _column_kind(query_result: QueryResult, index: int) -> str:
    """Infer a column's type from its first non-null value (no value is exposed)."""
    for row in query_result.rows:
        value = row[index]
        if value is None:
            continue
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int | float | Decimal):
            return "number"
        return "string"
    return "unknown"


def _describe_schema(query_result: QueryResult) -> str:
    """Render the result schema as ``- name: type`` lines, carrying no data values."""
    return "\n".join(
        f"- {name}: {_column_kind(query_result, i)}" for i, name in enumerate(query_result.columns)
    )


# An explicit user-requested presentation mandates its component, overriding the data-shape
# default — the user's stated wish wins (e.g. a "breakdown table" must be a DataTable even
# when the shape would otherwise suggest a bar chart).
_VIEW_HINT_GUIDANCE: dict[WidgetViewHint, str] = {
    "table": (
        "The user explicitly asked for this as a TABLE: author a DataTable of the result rows."
    ),
    "chart": (
        "The user explicitly asked for this as a CHART: author a ChartJs, choosing the kind "
        "(line for a time/ordered axis, bar for categories, pie only for a parts-of-a-whole "
        "breakdown of at most 5 rows) by the data shape above."
    ),
    "kpi": (
        "The user explicitly asked for this as a KPI: author a KpiStat showing the single "
        "headline value (set valueColumn to that column and label it)."
    ),
}


def _element_guidance(role: WidgetRole, view_hint: WidgetViewHint | None) -> str:
    """The element the worker must author, from an explicit view hint or the widget's role.

    An explicit ``view_hint`` (the user asked for a table/chart/kpi) mandates that component.
    Otherwise a ``metric`` widget is a headline number → a KpiStat is mandated (the host already
    placed it in the KPI band); an ``analysis`` widget picks chart-vs-table by data shape — the
    worker alone sees the result, so it keeps that judgement.
    """
    if view_hint is not None:
        return _VIEW_HINT_GUIDANCE[view_hint]
    if role == "metric":
        return (
            "Author a KpiStat showing this one headline number: set valueColumn to the metric "
            "column and label it. The result is a single row."
        )
    return (
        "Author ONE visualization element that best presents this widget, choosing by the data "
        "shape above. If the result is a SINGLE row, it is a headline answer, not a series — "
        "never chart it: author a KpiStat when the value is numeric, or a one-row DataTable "
        "when it is a label. For MULTIPLE rows: a category or time column with a numeric series "
        "-> ChartJs (line for a time/ordered axis, bar for categories, pie only for a "
        "parts-of-a-whole breakdown of at most 5 rows); many columns or a long detail list "
        "-> DataTable."
    )


def _build_human_content(
    title: str, role: WidgetRole, query_result: QueryResult, view_hint: WidgetViewHint | None
) -> str:
    """Build the widget-authoring prompt: title + schema + role/hint, never the rows themselves."""
    return (
        f"Widget: {title}\n\n"
        f"Result schema (column: type), {query_result.row_count} rows — values withheld:\n"
        f"{_describe_schema(query_result)}\n\n"
        f"{_element_guidance(role, view_hint)} "
        'Append it to "/elements/root/children/-". Bind its data prop to '
        f'{{"$state":"{_DATA_ROOT}/rows"}} (or {{"$state":"{_DATA_ROOT}"}} for a table) and '
        "reference columns by name. Emit one JSON patch per line and nothing else."
    )


class GenerateWidgetView:
    """Authors one widget's namespaced view patches (data bound via ``$state``).

    Example:
        view = GenerateWidgetView(model, system_prompt, extractor)
        lines = view.author("widget-0", "Amount by category", "analysis", query_result)
    """

    def __init__(
        self,
        chat_model: BaseChatModel,
        system_prompt: str,
        content_extractor: ResponseContentExtractor,
    ) -> None:
        """Wire the chat model, the catalog-derived system prompt, and a text extractor."""
        self._model: Runnable[LanguageModelInput, BaseMessage] = chat_model.with_config(
            {"tags": [step_tag("generate_widget_view")]}
        )
        self._system_prompt = system_prompt
        self._extractor = content_extractor

    def author(
        self,
        widget_id: str,
        title: str,
        role: WidgetRole,
        query_result: QueryResult,
        view_hint: WidgetViewHint | None = None,
    ) -> list[str]:
        """Author and namespace one widget's SpecStream patch lines, placed by its role.

        ``view_hint`` mandates the component when the user asked for one; otherwise the
        worker chooses by role and data shape.
        """
        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=_build_human_content(title, role, query_result, view_hint)),
        ]
        text = self._extractor.extract(self._model.invoke(messages))
        lines = keep_valid_patch_lines(text) or _fallback_table_lines()
        return namespace_widget_patches(lines, widget_id, role)
