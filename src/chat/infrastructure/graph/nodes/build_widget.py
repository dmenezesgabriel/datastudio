"""LangGraph worker node: build one dashboard widget end-to-end.

A ``build_widget`` worker is spawned per planned widget (via ``Send``) and runs that
widget's own SQL pipeline — generate → execute → repair loop — then authors the
widget's view. Reusing the existing SQL nodes as plain callables on a local state
keeps the per-widget pipeline in one place; parallel workers append their outputs to
the ``widget_views`` / ``widget_results`` reducer channels without clobbering.
"""

import json
from collections.abc import Mapping
from typing import cast

from langchain_core.language_models import BaseChatModel

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.widget import WidgetResult, WidgetSpec
from chat.infrastructure.graph.nodes.execute_sql import ExecuteSql
from chat.infrastructure.graph.nodes.generate_sql import GenerateSql
from chat.infrastructure.graph.nodes.generate_widget_view import (
    GenerateWidgetView,
    namespace_widget_patches,
)
from chat.infrastructure.graph.nodes.repair_sql import MAX_REPAIR_ATTEMPTS, RepairSql
from chat.infrastructure.graph.response_content_extractor import (
    ResponseContentExtractor,
)
from shared.application.ports.sql_engine_port import SqlEnginePort
from shared.domain.value_objects.query_result import QueryResult


def _attempts(state: Mapping[str, object]) -> int:
    """Read the current repair attempt count (0 when absent)."""
    value = state.get("repair_attempts")
    return value if isinstance(value, int) else 0


def run_sql_with_repair(
    state: dict[str, object],
    generate_sql: GenerateSql,
    execute_sql: ExecuteSql,
    repair_sql: RepairSql,
) -> dict[str, object]:
    """Generate, execute, and repair SQL on a local state until it runs or attempts run out.

    Mirrors the main graph's generate_sql → execute_sql → (repair → execute) loop, but
    imperatively over a per-widget local state so it can run inside a parallel worker.
    """
    state = {**state, **generate_sql(cast(ChatState, state))}
    state = {**state, **execute_sql(cast(ChatState, state))}
    while state.get("query_result") is None and _attempts(state) < MAX_REPAIR_ATTEMPTS:
        state = {**state, **repair_sql(cast(ChatState, state))}
        state = {**state, **execute_sql(cast(ChatState, state))}
    return state


class BuildWidget:
    """Worker that turns one WidgetSpec into namespaced view patches + its result.

    Example:
        worker = BuildWidget(chat_model, engine, view_model, prompt, extractor)
        worker({"widget": WidgetSpec(...), "schema": "...", "tables": ["events"]})
        # → {"widget_views": [...], "widget_results": [WidgetResult(...)]}
    """

    def __init__(
        self,
        chat_model: BaseChatModel,
        sql_engine: SqlEnginePort,
        view_model: BaseChatModel,
        system_prompt: str,
        content_extractor: ResponseContentExtractor,
    ) -> None:
        """Wire the per-widget SQL pipeline and the view-authoring model."""
        self._generate_sql = GenerateSql(chat_model)
        self._execute_sql = ExecuteSql(sql_engine)
        self._repair_sql = RepairSql(chat_model, sql_engine)
        self._view = GenerateWidgetView(view_model, system_prompt, content_extractor)

    def __call__(self, state: ChatState) -> dict[str, object]:
        """Run this widget's SQL pipeline, then author its namespaced view."""
        widget = cast(WidgetSpec, cast(dict[str, object], state)["widget"])
        local: dict[str, object] = {
            "question": widget.sub_question,
            "schema": state["schema"],
            "tables": cast(dict[str, object], state).get("tables", []),
        }
        local = run_sql_with_repair(local, self._generate_sql, self._execute_sql, self._repair_sql)
        result = local.get("query_result")
        if not isinstance(result, QueryResult):
            return {"widget_views": _failure_widget(widget)}
        sql = local.get("sql_query")
        return {
            "widget_views": self._view.author(widget.id, widget.title, result),
            "widget_results": [
                WidgetResult(
                    widget_id=widget.id,
                    title=widget.title,
                    result=result,
                    sql=sql if isinstance(sql, str) else "",
                )
            ],
        }


def _failure_widget(widget: WidgetSpec) -> list[str]:
    """A namespaced note element shown when a widget's SQL never succeeds."""
    element: dict[str, object] = {
        "type": "Markdown",
        "props": {"text": f"_Couldn't build “{widget.title}”._"},
        "children": [],
    }
    lines = [
        json.dumps({"op": "add", "path": "/elements/note", "value": element}),
        json.dumps({"op": "add", "path": "/elements/root/children/-", "value": "note"}),
    ]
    return namespace_widget_patches(lines, widget.id)
