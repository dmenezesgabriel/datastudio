"""LangGraph worker node: build one dashboard widget end-to-end.

A ``build_widget`` worker is spawned per planned widget (via ``Send``) and runs that
widget's own SQL pipeline — generate → execute → repair loop — then authors the
widget's view. Reusing the existing SQL nodes as plain callables on a local state
keeps the per-widget pipeline in one place; parallel workers append their outputs to
the ``widget_patch_lines`` / ``widget_results`` reducer channels without clobbering.
"""

import json
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from typing import cast

from langchain_core.language_models import BaseChatModel

from chat.application.ports.progress_reporter import ProgressReporter
from chat.domain.value_objects.stream_event import ProgressStep
from chat.domain.value_objects.widget import WidgetResult, WidgetSpec
from chat.infrastructure.graph.chat_state import ChatState
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


@contextmanager
def _sub_step(
    reporter: ProgressReporter, widget_id: str, sub: str, label: str
) -> Generator[None, None, None]:
    """Bracket a widget sub-step with running/done progress under the widget's parent."""
    step_id = f"{widget_id}:{sub}"
    reporter.report(ProgressStep(step_id, label, "running", parent_id=widget_id))
    yield
    reporter.report(ProgressStep(step_id, label, "done", parent_id=widget_id))


def run_sql_with_repair(
    state: dict[str, object],
    generate_sql: GenerateSql,
    execute_sql: ExecuteSql,
    repair_sql: RepairSql,
    reporter: ProgressReporter,
    widget_id: str,
) -> dict[str, object]:
    """Generate, execute, and repair SQL on a local state until it runs or attempts run out.

    Mirrors the main graph's generate_sql → execute_sql → (repair → execute) loop, but
    imperatively over a per-widget local state so it can run inside a parallel worker.
    Each stage reports a checklist sub-step nested under ``widget_id``.
    """
    with _sub_step(reporter, widget_id, "sql", "Generating SQL"):
        state = {**state, **generate_sql(cast(ChatState, state))}
    with _sub_step(reporter, widget_id, "query", "Running query"):
        state = {**state, **execute_sql(cast(ChatState, state))}
    return _repair_until_runs(state, execute_sql, repair_sql, reporter, widget_id)


def _repair_until_runs(
    state: dict[str, object],
    execute_sql: ExecuteSql,
    repair_sql: RepairSql,
    reporter: ProgressReporter,
    widget_id: str,
) -> dict[str, object]:
    """Retry SQL via the repair loop until it runs or attempts run out (reports "Repairing SQL")."""
    while state.get("query_result") is None and _attempts(state) < MAX_REPAIR_ATTEMPTS:
        with _sub_step(reporter, widget_id, "repair", "Repairing SQL"):
            state = {**state, **repair_sql(cast(ChatState, state))}
            state = {**state, **execute_sql(cast(ChatState, state))}
    return state


class BuildWidget:
    """Worker that turns one WidgetSpec into namespaced view patches + its result.

    Example:
        worker = BuildWidget(chat_model, engine, view_model, prompt, extractor, reporter)
        worker({"widget": WidgetSpec(...), "schema": "...", "tables": ["events"]})
        # → {"widget_patch_lines": [...], "widget_results": [WidgetResult(...)]}
    """

    def __init__(
        self,
        chat_model: BaseChatModel,
        sql_engine: SqlEnginePort,
        view_model: BaseChatModel,
        system_prompt: str,
        content_extractor: ResponseContentExtractor,
        reporter: ProgressReporter,
    ) -> None:
        """Wire the per-widget SQL pipeline, the view-authoring model, and the reporter."""
        self._generate_sql = GenerateSql(chat_model)
        self._execute_sql = ExecuteSql(sql_engine)
        self._repair_sql = RepairSql(chat_model, sql_engine)
        self._view = GenerateWidgetView(view_model, system_prompt, content_extractor)
        self._reporter = reporter

    def __call__(self, state: ChatState) -> dict[str, object]:
        """Run this widget's SQL pipeline, then author its namespaced view."""
        widget = cast(WidgetSpec, cast(dict[str, object], state)["widget"])
        label = f'Building "{widget.title}"'
        self._reporter.report(ProgressStep(widget.id, label, "running"))
        local = self._run_pipeline(widget, state)
        result = local.get("query_result")
        if not isinstance(result, QueryResult):
            self._reporter.report(ProgressStep(widget.id, label, "failed"))
            return {"widget_patch_lines": _failure_widget(widget)}
        views = self._author_patch_lines(widget, result)
        self._reporter.report(ProgressStep(widget.id, label, "done"))
        return {
            "widget_patch_lines": views,
            "widget_results": [self._result(widget, result, local)],
        }

    def _run_pipeline(self, widget: WidgetSpec, state: ChatState) -> dict[str, object]:
        """Run the per-widget SQL generate → execute → repair loop on a local state."""
        local: dict[str, object] = {
            "question": widget.sub_question,
            "schema": state["schema"],
            "tables": cast(dict[str, object], state).get("tables", []),
        }
        return run_sql_with_repair(
            local,
            self._generate_sql,
            self._execute_sql,
            self._repair_sql,
            self._reporter,
            widget.id,
        )

    def _author_patch_lines(self, widget: WidgetSpec, result: QueryResult) -> list[str]:
        """Author the widget's namespaced view, reporting a "Building chart" sub-step."""
        with _sub_step(self._reporter, widget.id, "view", "Building chart"):
            return self._view.author(widget.id, widget.title, result)

    def _result(
        self, widget: WidgetSpec, result: QueryResult, local: Mapping[str, object]
    ) -> WidgetResult:
        """Assemble the widget's result (rows + SQL) for the /state patch and disclosure."""
        sql = local.get("sql_query")
        return WidgetResult(
            widget_id=widget.id,
            title=widget.title,
            result=result,
            sql=sql if isinstance(sql, str) else "",
        )


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
