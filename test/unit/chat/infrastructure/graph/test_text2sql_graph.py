from langgraph.graph.state import CompiledStateGraph  # pyright: ignore[reportMissingTypeStubs]

from shared.domain.value_objects.query_result import QueryResult
from chat.infrastructure.graph.text2sql_graph import build_text2sql_graph
from chat.infrastructure.graph.types import TypedChatGraph
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)

_EXPECTED_NODES = frozenset(
    {
        "classify_query",
        "list_tables",
        "select_tables",
        "get_schema",
        "generate_sql",
        "execute_sql",
        "format_response",
        "decompose_query",
        "synthesize_answer",
    }
)
_EXPECTED_SIMPLE_EDGES = frozenset(
    {
        ("__start__", "classify_query"),
        ("classify_query", "list_tables"),
        ("list_tables", "select_tables"),
        ("select_tables", "get_schema"),
        # get_schema → generate_sql / decompose_query are conditional — not here
        ("generate_sql", "execute_sql"),
        ("execute_sql", "format_response"),
        ("format_response", "__end__"),
        ("decompose_query", "synthesize_answer"),
        ("synthesize_answer", "__end__"),
    }
)


def _make_graph() -> TypedChatGraph:
    chat_model = FakeStructuredChatModel(
        sql="SELECT 1", answer="One row.", tables=["orders"], complexity="simple"
    )
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


class TestFormatModelInjection:
    def test_format_response_uses_separate_model_when_provided(self) -> None:
        # arrange — two distinct models; only the format model has the answer
        sql_model = FakeStructuredChatModel(
            sql="SELECT 1", tables=["orders"], complexity="simple"
        )
        format_model = FakeStructuredChatModel(
            answer="One row.", sql="SELECT 1", tables=["orders"]
        )
        sql_engine = FakeSqlEngine(
            tables=["orders"],
            schemas={"orders": "-- orders\nid INT"},
            query_result=QueryResult(columns=["id"], rows=[(1,)], row_count=1),
        )
        graph = build_text2sql_graph(
            sql_model, sql_engine, format_chat_model=format_model
        )
        # act
        result = graph.invoke({"question": "How many?"})  # pyright: ignore[reportUnknownMemberType]
        # assert — format model was invoked (its answer field is in the response)
        assert result["response"] == "One row."
        assert format_model.last_runnable.last_messages  # format model was called


class TestGraphTopology:
    """Verifies that all expected nodes are wired and reachable in the compiled graph."""

    def test_all_nodes_are_registered(self) -> None:
        # arrange / act
        graph = _make_graph()
        # assert — builder.nodes holds the spec dict keyed by node name
        registered = frozenset(graph.builder.nodes.keys())
        assert registered == _EXPECTED_NODES

    def test_non_conditional_edges_are_correct(self) -> None:
        # arrange / act
        graph = _make_graph()
        # assert — conditional edges (classify_query routing) are in builder.branches,
        # not builder.edges; only check deterministic edges here
        edges = frozenset((src, dst) for src, dst in graph.builder.edges)
        assert edges == _EXPECTED_SIMPLE_EDGES

    def test_get_schema_has_conditional_branches(self) -> None:
        # arrange / act
        graph = _make_graph()
        # assert — routing targets are registered as branches from get_schema
        branches = graph.builder.branches.get("get_schema", {})
        assert branches  # at least one branch defined from get_schema

    def test_simple_path_routes_to_list_tables(self) -> None:
        # arrange — complexity="simple" routes through the standard pipeline
        chat_model = FakeStructuredChatModel(
            sql="SELECT 1",
            answer="Simple answer.",
            tables=["orders"],
            complexity="simple",
        )
        sql_engine = FakeSqlEngine(
            tables=["orders"],
            schemas={"orders": "-- orders\nid INT"},
            query_result=QueryResult(columns=["id"], rows=[(1,)], row_count=1),
        )
        graph = build_text2sql_graph(chat_model, sql_engine)
        # act
        result = graph.invoke({"question": "How many?"})  # pyright: ignore[reportUnknownMemberType]
        # assert — format_response produced the answer
        assert result["response"] == "Simple answer."

    def test_complex_path_routes_to_decompose_query(self) -> None:
        # arrange — complexity="complex" routes through decompose_query → synthesize_answer
        chat_model = FakeStructuredChatModel(
            sql="SELECT AVG(m) FROM cars",
            answer="Improved by 10 MPG.",
            tables=["cars"],
            complexity="complex",
            sub_questions=["Avg MPG 1970?", "Avg MPG 1980?"],
        )
        sql_engine = FakeSqlEngine(
            tables=["cars"],
            schemas={"cars": "-- cars\nMiles_per_Gallon FLOAT"},
            query_result=QueryResult(columns=["avg"], rows=[(20.0,)], row_count=1),
        )
        graph = build_text2sql_graph(chat_model, sql_engine)
        # act
        result = graph.invoke({"question": "By how many MPG did cars improve?"})  # pyright: ignore[reportUnknownMemberType]
        # assert — synthesize_answer produced the answer (same fake model → same answer field)
        assert result["response"] == "Improved by 10 MPG."
