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
        assert graph.last_input == {"question": "How many orders?"}

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
