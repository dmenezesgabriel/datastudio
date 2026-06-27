from typing import cast

from chat.infrastructure.graph.text2sql_engine_adapter import Text2SqlEngineAdapter
from chat.infrastructure.graph.types import TypedChatGraph
from chat.infrastructure.graph.view.render_tree_builder import narrative_tree
from test.unit.chat.infrastructure.graph.fake_chat_graph import FakeChatGraph


def _adapter(graph: FakeChatGraph, timeout_s: float | None = None) -> Text2SqlEngineAdapter:
    return Text2SqlEngineAdapter(cast(TypedChatGraph, graph), timeout_s=timeout_s)


class TestText2SqlEngineAdapter:
    def test_maps_state_to_result(self) -> None:
        # arrange
        view = narrative_tree("There are 42 orders.")
        graph = FakeChatGraph(
            {"response": "There are 42 orders.", "sql_query": "SELECT 1", "view": view}
        )
        # act
        result = _adapter(graph).answer("How many orders?")
        # assert
        assert result.response == "There are 42 orders."
        assert result.sql_query == "SELECT 1"
        assert result.view is view
        assert graph.last_input["question"] == "How many orders?"
        assert "request_id" in graph.last_input

    def test_defaults_view_when_missing(self) -> None:
        # arrange — state without a view (e.g. an early failure)
        graph = FakeChatGraph({"response": "Could not answer.", "sql_query": ""})
        # act
        result = _adapter(graph).answer("bad question")
        # assert — a narrative-only tree is synthesized from the response
        assert result.view.elements["narrative"].props["text"] == "Could not answer."


class TestText2SqlEngineAdapterTimeout:
    def test_returns_graceful_result_on_timeout(self) -> None:
        # arrange — graph runs longer than the timeout
        graph = FakeChatGraph({"response": "late", "sql_query": "x"}, delay_s=0.05)
        # act
        result = _adapter(graph, timeout_s=0.01).answer("slow question")
        # assert — graceful message, not the (eventual) graph output
        assert "longer than expected" in result.response
        assert result.sql_query == ""

    def test_timeout_result_has_non_none_view(self) -> None:
        # kills _timeout_result__mutmut_3 (view=None)
        graph = FakeChatGraph({"response": "late", "sql_query": "x"}, delay_s=0.05)
        result = _adapter(graph, timeout_s=0.01).answer("slow question")
        assert result.view is not None

    def test_timeout_result_view_contains_timeout_message(self) -> None:
        # kills _timeout_result__mutmut_8: narrative_tree(None) vs correct arg
        graph = FakeChatGraph({"response": "late", "sql_query": "x"}, delay_s=0.05)
        result = _adapter(graph, timeout_s=0.01).answer("slow question")
        # The narrative element must contain the actual timeout message
        assert "longer than expected" in result.view.elements["narrative"].props["text"]


class TestText2SqlToResult:
    def test_non_string_sql_query_defaults_to_empty_string(self) -> None:
        # kills _to_result__mutmut_23 (else "XXXX" instead of else "")
        # arrange — state where sql_query is an int (not a str)
        view = narrative_tree("answer")
        graph = FakeChatGraph({"response": "answer", "sql_query": 0, "view": view})
        result = _adapter(graph).answer("q")
        assert result.sql_query == ""
