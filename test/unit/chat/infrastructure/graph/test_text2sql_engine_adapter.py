"""Tests for the sync answer() path (CLI), which compiles widget views into a result."""

import json
from typing import cast

from chat.domain.value_objects.widget import WidgetResult
from chat.infrastructure.graph.text2sql_engine_adapter import Text2SqlEngineAdapter
from chat.infrastructure.graph.types import TypedChatGraph
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.fake_chat_graph import FakeChatGraph


def _adapter(graph: FakeChatGraph, timeout_s: float | None = None) -> Text2SqlEngineAdapter:
    return Text2SqlEngineAdapter(cast(TypedChatGraph, graph), timeout_s=timeout_s)


def _widget_result(widget_id: str) -> WidgetResult:
    return WidgetResult(
        widget_id=widget_id,
        title="Count",
        result=QueryResult(columns=["n"], rows=[(1,)], row_count=1),
        sql=f"SELECT {widget_id}",
    )


def _view_line(widget_id: str) -> str:
    return json.dumps(
        {"op": "add", "path": f"/elements/{widget_id}-chart", "value": {"type": "ChartJs"}}
    )


class TestText2SqlEngineAdapter:
    def test_compiles_aggregated_widget_views(self) -> None:
        # arrange — the final state holds aggregated widget views + results
        graph = FakeChatGraph(
            {
                "narrative": "Two widgets.",
                "widget_patch_lines": [_view_line("widget-0"), _view_line("widget-1")],
                "widget_results": [_widget_result("widget-0"), _widget_result("widget-1")],
            }
        )
        # act
        result = _adapter(graph).answer("overview")
        # assert
        assert result.narrative == "Two widgets."
        assert result.view.elements["narrative"].props["text"] == "Two widgets."
        assert "widget-0-chart" in result.view.elements
        assert graph.last_input["question"] == "overview"
        # The CLI path is stateless: it seeds an empty conversation history.
        assert graph.last_input["history"] == []

    def test_defaults_to_narrative_only_without_widgets(self) -> None:
        graph = FakeChatGraph({"narrative": "Could not answer."})
        result = _adapter(graph).answer("bad")
        assert result.view.elements["narrative"].props["text"] == "Could not answer."


class TestText2SqlEngineAdapterTimeout:
    def test_returns_graceful_result_on_timeout(self) -> None:
        graph = FakeChatGraph({"narrative": "late"}, delay_s=0.05)
        result = _adapter(graph, timeout_s=0.01).answer("slow")
        assert "longer than expected" in result.narrative
        assert "longer than expected" in result.view.elements["narrative"].props["text"]
