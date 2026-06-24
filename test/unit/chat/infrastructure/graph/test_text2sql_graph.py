from langgraph.graph.state import CompiledStateGraph  # pyright: ignore[reportMissingTypeStubs]

from shared.domain.value_objects.query_result import QueryResult
from chat.infrastructure.graph.text2sql_graph import build_text2sql_graph
from chat.infrastructure.graph.types import TypedChatGraph
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)

_EXPECTED_NODES = frozenset(
    {"list_tables", "get_schema", "generate_sql", "execute_sql", "format_response"}
)
_EXPECTED_EDGES = frozenset(
    {
        ("__start__", "list_tables"),
        ("list_tables", "get_schema"),
        ("get_schema", "generate_sql"),
        ("generate_sql", "execute_sql"),
        ("execute_sql", "format_response"),
        ("format_response", "__end__"),
    }
)


def _make_graph() -> TypedChatGraph:
    chat_model = FakeStructuredChatModel(sql="SELECT 1", answer="One row.")
    sql_engine = FakeSqlEngine(
        tables=["orders"],
        schemas={"orders": "-- orders\nid INT"},
        query_result=QueryResult(columns=["id"], rows=[(1,)], row_count=1),
    )
    return build_text2sql_graph(chat_model, sql_engine)


class TestBuildText2SqlGraph:
    def test_returns_compiled_state_graph(self) -> None:
        # arrange / act
        graph = _make_graph()
        # assert
        assert isinstance(graph, CompiledStateGraph)

    def test_invoke_returns_response_key(self) -> None:
        # arrange
        graph = _make_graph()
        # act
        result = graph.invoke({"question": "How many?"})  # pyright: ignore[reportUnknownMemberType]
        # assert
        assert result["response"] == "One row."

    def test_invoke_propagates_tables_through_state(self) -> None:
        # arrange
        graph = _make_graph()
        # act
        result = graph.invoke({"question": "q"})  # pyright: ignore[reportUnknownMemberType]
        # assert
        assert result["tables"] == ["orders"]


class TestGraphTopology:
    """Verifies that all expected nodes are wired and reachable in the compiled graph."""

    def test_all_five_nodes_are_registered(self) -> None:
        # arrange / act
        graph = _make_graph()
        # assert — builder.nodes holds the spec dict keyed by node name
        registered = frozenset(graph.builder.nodes.keys())
        assert registered == _EXPECTED_NODES

    def test_graph_edges_contain_all_expected_connections(self) -> None:
        # arrange / act
        graph = _make_graph()
        # assert — builder.edges order is not guaranteed; compare as a set of pairs
        edges = frozenset((src, dst) for src, dst in graph.builder.edges)
        assert edges == _EXPECTED_EDGES
