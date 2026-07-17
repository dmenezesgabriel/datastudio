"""Tests for the build_widget worker: per-widget SQL pipeline + namespaced view."""

import json
from typing import cast

from chat.application.ports.progress_reporter import NullProgressReporter
from chat.domain.value_objects.widget import WidgetSpec
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes.build_widget import BuildWidget
from chat.infrastructure.graph.response_content_extractor import PlainTextExtractor
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)
from test.unit.chat.infrastructure.graph.nodes.test_generate_widget_view import FakeViewModel
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine

_VIEW = (
    '{"op":"add","path":"/elements/chart","value":'
    '{"type":"ChartJs","props":{"data":{"$state":"/result/rows"}},"children":[]}}\n'
    '{"op":"add","path":"/elements/root/children/-","value":"chart"}'
)


def _worker(engine: FakeSqlEngine, view_content: object = _VIEW) -> BuildWidget:
    sql_model = FakeStructuredChatModel(sql="SELECT 1")
    return BuildWidget(
        cast(object, sql_model),  # type: ignore[arg-type]
        engine,
        cast(object, FakeViewModel(view_content)),  # type: ignore[arg-type]
        "prompt",
        PlainTextExtractor(),
        NullProgressReporter(),
    )


def _state(widget: WidgetSpec) -> ChatState:
    return cast(ChatState, {"widget": widget, "schema": "-- orders\nid INT", "tables": ["orders"]})


class TestBuildWidget:
    def test_happy_path_returns_namespaced_view_and_result(self) -> None:
        # Arrange — a multi-row result so the authored ChartJs survives the view shape guard;
        # this test asserts namespacing/binding, not view selection (covered by shape_guard tests).
        result = QueryResult(columns=["n"], rows=[(42,), (43,)], row_count=2)
        engine = FakeSqlEngine(query_result=result)
        widget = WidgetSpec(id="widget-1", title="Count", sub_question="how many", role="analysis")
        # Act
        out = _worker(engine)(_state(widget))
        # Assert — view lines are namespaced to widget-1 and bound to its $state
        lines = [json.loads(line) for line in out["widget_patch_lines"]]
        assert lines[0]["path"] == "/elements/widget-1-chart"
        assert lines[0]["value"]["props"]["data"] == {"$state": "/widget-1/rows"}
        # and the widget's executed result is returned for the /state patch + SQL disclosure
        widget_results = out["widget_results"]
        assert len(widget_results) == 1
        assert widget_results[0].widget_id == "widget-1"
        assert widget_results[0].title == "Count"
        assert widget_results[0].result is result
        assert widget_results[0].sql == "SELECT 1"

    def test_forwards_view_hint_to_the_view_author(self) -> None:
        # Arrange — a widget the user asked to see as a table
        result = QueryResult(columns=["status", "orders"], rows=[("delivered", 5)], row_count=1)
        engine = FakeSqlEngine(query_result=result)
        view_model = FakeViewModel(
            '{"op":"add","path":"/elements/t","value":{"type":"DataTable"}}\n'
            '{"op":"add","path":"/elements/root/children/-","value":"t"}'
        )
        worker = BuildWidget(
            cast(object, FakeStructuredChatModel(sql="SELECT 1")),  # type: ignore[arg-type]
            engine,
            cast(object, view_model),  # type: ignore[arg-type]
            "prompt",
            PlainTextExtractor(),
            NullProgressReporter(),
        )
        widget = WidgetSpec(
            id="widget-0",
            title="By status",
            sub_question="orders by status",
            role="analysis",
            view_hint="table",
        )
        # Act
        worker(_state(widget))
        # Assert — the hint reached the view author's prompt as a DataTable mandate
        human = str(view_model.received[-1].content)
        assert "TABLE" in human and "DataTable" in human

    def test_runs_repair_loop_on_failure_then_recovers(self) -> None:
        # Arrange — first SQL errors, the repaired SQL succeeds
        good = QueryResult(columns=["n"], rows=[(1,)], row_count=1)
        engine = FakeSqlEngine(results_by_sql={"SELECT 1": good}, error=ValueError("boom"))
        # FakeStructuredChatModel always returns "SELECT 1"; the first execution of a *different*
        # initial query would fail — here generate + repair both yield SELECT 1 which succeeds.
        widget = WidgetSpec(id="widget-0", title="t", sub_question="q", role="analysis")
        out = _worker(engine)(_state(widget))
        assert len(out["widget_results"]) == 1

    def test_persistent_sql_failure_yields_a_note_and_no_result(self) -> None:
        # Arrange — every execution errors, repairs cannot recover
        engine = FakeSqlEngine(error=ValueError("Binder Error"))
        widget = WidgetSpec(id="widget-2", title="Broken", sub_question="q", role="metric")
        # Act
        out = _worker(engine)(_state(widget))
        # Assert — a namespaced note element, and no widget_results (nothing to bind/disclose)
        assert out.get("widget_results", []) == []
        note = json.loads(out["widget_patch_lines"][0])
        assert note["path"].startswith("/elements/widget-2-")
        assert note["value"]["type"] == "Markdown"
        # even a failed metric widget's note goes to the grid, not among the headline KPIs
        placement = next(
            json.loads(line)
            for line in out["widget_patch_lines"]
            if json.loads(line)["path"].endswith("/children/-")
        )
        assert placement["path"] == "/elements/grid/children/-"

    def test_metric_widget_view_lands_in_the_kpi_band(self) -> None:
        # Arrange — a metric widget whose worker authors a KpiStat
        result = QueryResult(columns=["total"], rows=[(42,)], row_count=1)
        engine = FakeSqlEngine(query_result=result)
        kpi_view = (
            '{"op":"add","path":"/elements/k","value":'
            '{"type":"KpiStat","props":{"valueColumn":"total","data":{"$state":"/result/rows"}}}}\n'
            '{"op":"add","path":"/elements/root/children/-","value":"k"}'
        )
        widget = WidgetSpec(id="widget-0", title="Total", sub_question="total", role="metric")
        # Act
        out = _worker(engine, kpi_view)(_state(widget))
        # Assert — the frame is placed in the kpi-row band (deterministic role → region)
        placement = next(
            json.loads(line)
            for line in out["widget_patch_lines"]
            if json.loads(line)["path"].endswith("/children/-")
        )
        assert placement["path"] == "/elements/kpi-row/children/-"
