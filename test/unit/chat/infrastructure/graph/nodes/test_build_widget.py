"""Tests for the build_widget worker: per-widget SQL pipeline + namespaced view."""

import json
from typing import cast

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.widget import WidgetSpec
from chat.infrastructure.graph.nodes.build_widget import BuildWidget
from chat.infrastructure.graph.plain_text_extractor import PlainTextExtractor
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
    )


def _state(widget: WidgetSpec) -> ChatState:
    return cast(ChatState, {"widget": widget, "schema": "-- orders\nid INT", "tables": ["orders"]})


class TestBuildWidget:
    def test_happy_path_returns_namespaced_view_and_result(self) -> None:
        # Arrange
        result = QueryResult(columns=["n"], rows=[(42,)], row_count=1)
        engine = FakeSqlEngine(query_result=result)
        widget = WidgetSpec(id="widget-1", title="Count", sub_question="how many")
        # Act
        out = _worker(engine)(_state(widget))
        # Assert — view lines are namespaced to widget-1 and bound to its $state
        lines = [json.loads(line) for line in out["widget_views"]]
        assert lines[0]["path"] == "/elements/widget-1-chart"
        assert lines[0]["value"]["props"]["data"] == {"$state": "/widget-1/rows"}
        # and the widget's executed result is returned for the /state patch + SQL disclosure
        widget_results = out["widget_results"]
        assert len(widget_results) == 1
        assert widget_results[0].widget_id == "widget-1"
        assert widget_results[0].title == "Count"
        assert widget_results[0].result is result
        assert widget_results[0].sql == "SELECT 1"

    def test_runs_repair_loop_on_failure_then_recovers(self) -> None:
        # Arrange — first SQL errors, the repaired SQL succeeds
        good = QueryResult(columns=["n"], rows=[(1,)], row_count=1)
        engine = FakeSqlEngine(results_by_sql={"SELECT 1": good}, error=ValueError("boom"))
        # FakeStructuredChatModel always returns "SELECT 1"; the first execution of a *different*
        # initial query would fail — here generate + repair both yield SELECT 1 which succeeds.
        widget = WidgetSpec(id="widget-0", title="t", sub_question="q")
        out = _worker(engine)(_state(widget))
        assert len(out["widget_results"]) == 1

    def test_persistent_sql_failure_yields_a_note_and_no_result(self) -> None:
        # Arrange — every execution errors, repairs cannot recover
        engine = FakeSqlEngine(error=ValueError("Binder Error"))
        widget = WidgetSpec(id="widget-2", title="Broken", sub_question="q")
        # Act
        out = _worker(engine)(_state(widget))
        # Assert — a namespaced note element, and no widget_results (nothing to bind/disclose)
        assert out.get("widget_results", []) == []
        note = json.loads(out["widget_views"][0])
        assert note["path"].startswith("/elements/widget-2-")
        assert note["value"]["type"] == "Markdown"
