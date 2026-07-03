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

from chat.infrastructure.graph.observability import step_tag
from chat.infrastructure.graph.response_content_extractor import (
    ResponseContentExtractor,
)
from chat.infrastructure.graph.spec_patch import parse_patch
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


def load_catalog_prompt() -> str:
    """Load the catalog-derived system prompt that constrains the view-authoring model."""
    return _CATALOG_PROMPT_PATH.read_text(encoding="utf-8")


def _is_reserved(path: str) -> bool:
    """True when a patch path targets a backend-owned element (narrative/root/sql)."""
    return path in _RESERVED_EXACT or path.startswith(_RESERVED_PREFIXES)


def valid_view_patch_lines(text: str) -> list[str]:
    r"""Keep only well-formed, non-reserved JSON-Patch lines from raw model output.

    Example:
        valid_view_patch_lines('{"op":"add","path":"/elements/x","value":1}\nthanks')
    """
    kept: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
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


def namespace_widget_patches(lines: list[str], widget_id: str) -> list[str]:
    """Prefix element ids/child-refs with the widget id and rebind ``$state`` to it.

    Keeps parallel widgets from colliding on shared element ids and binds each to its
    own streamed ``/state/<widget_id>`` data.
    """
    out: list[str] = []
    for line in lines:
        patch = parse_patch(line)
        if patch is None or not isinstance(patch.get("path"), str):
            continue
        path = cast(str, patch["path"])
        if path == "/elements/root/children/-":
            child = patch.get("value")
            if isinstance(child, str):
                out.append(_patch("add", path, f"{widget_id}-{child}"))
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


def _build_human_content(title: str, query_result: QueryResult) -> str:
    """Build the widget-authoring prompt: title + schema, never the rows themselves."""
    return (
        f"Widget: {title}\n\n"
        f"Result schema (column: type), {query_result.row_count} rows — values withheld:\n"
        f"{_describe_schema(query_result)}\n\n"
        "Author ONE visualization element (KpiStat, ChartJs, or DataTable) that best presents "
        "this widget, choosing by the data shape above: a single row -> KpiStat; a category "
        "or time column with a numeric series -> ChartJs (line for a time/ordered axis, bar "
        "for categories, pie only for a parts-of-a-whole breakdown of at most 5 rows); "
        "many columns or a long detail list -> DataTable. "
        'Append it to "/elements/root/children/-". Bind its data prop to '
        f'{{"$state":"{_DATA_ROOT}/rows"}} (or {{"$state":"{_DATA_ROOT}"}} for a table) and '
        "reference columns by name. Emit one JSON patch per line and nothing else."
    )


class GenerateWidgetView:
    """Authors one widget's namespaced view patches (data bound via ``$state``).

    Example:
        view = GenerateWidgetView(model, system_prompt, extractor)
        lines = view.author("widget-0", "Amount by category", query_result)
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

    def author(self, widget_id: str, title: str, query_result: QueryResult) -> list[str]:
        """Author and namespace one widget's SpecStream patch lines."""
        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=_build_human_content(title, query_result)),
        ]
        text = self._extractor.extract(self._model.invoke(messages))
        lines = valid_view_patch_lines(text) or _fallback_table_lines()
        return namespace_widget_patches(lines, widget_id)
