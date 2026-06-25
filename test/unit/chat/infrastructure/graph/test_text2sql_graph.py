"""Unit tests for build_text2sql_graph and wire_text2sql_graph."""

import inspect

from langgraph.graph.state import CompiledStateGraph  # pyright: ignore[reportMissingTypeStubs]

from chat.infrastructure.graph import text2sql_graph as graph_module
from chat.infrastructure.graph.text2sql_graph import build_text2sql_graph
from chat.infrastructure.graph.types import TypedChatGraph
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine

_EXPECTED_NODES = frozenset(
    {
        "list_tables",
        "select_tables",
        "get_schema",
        "generate_sql",
        "execute_sql",
        "repair_sql",
        "format_response",
    }
)
_EXPECTED_EDGES = frozenset(
    {
        ("__start__", "list_tables"),
        ("list_tables", "select_tables"),
        ("select_tables", "get_schema"),
        ("get_schema", "generate_sql"),
        ("generate_sql", "execute_sql"),
        # execute_sql → repair_sql / format_response is conditional — not here
        ("repair_sql", "execute_sql"),
        ("format_response", "__end__"),
    }
)


def _make_graph() -> TypedChatGraph:
    chat_model = FakeStructuredChatModel(sql="SELECT 1", answer="One row.", tables=["orders"])
    sql_engine = FakeSqlEngine(
        tables=["orders"],
        schemas={"orders": "-- orders\nid INT"},
        query_result=QueryResult(columns=["id"], rows=[(1,)], row_count=1),
    )
    return build_text2sql_graph(chat_model, sql_engine)


class TestBuildText2SqlGraph:
    """build_text2sql_graph returns a runnable compiled graph."""

    def test_returns_compiled_state_graph(self) -> None:
        """Return type is a CompiledStateGraph, ready for invoke()."""
        # arrange / act
        graph = _make_graph()
        # assert
        assert isinstance(graph, CompiledStateGraph)

    def test_invoke_returns_response_key(self) -> None:
        """Invoking the graph produces a natural-language response."""
        # arrange
        graph = _make_graph()
        # act
        result = graph.invoke({"question": "How many?"})  # pyright: ignore[reportUnknownMemberType]
        # assert
        assert result["response"] == "One row."

    def test_invoke_propagates_tables_through_state(self) -> None:
        """Tables listed by the engine flow through state to downstream nodes."""
        # arrange
        graph = _make_graph()
        # act
        result = graph.invoke({"question": "q"})  # pyright: ignore[reportUnknownMemberType]
        # assert
        assert result["tables"] == ["orders"]


class TestFormatModelInjection:
    """format_chat_model is used for table selection and response formatting."""

    def test_format_response_uses_separate_model_when_provided(self) -> None:
        """When format_chat_model is given, the format node uses it, not chat_model."""
        # arrange — two distinct models; only the format model has the answer
        sql_model = FakeStructuredChatModel(sql="SELECT 1", tables=["orders"])
        format_model = FakeStructuredChatModel(answer="One row.", sql="SELECT 1", tables=["orders"])
        sql_engine = FakeSqlEngine(
            tables=["orders"],
            schemas={"orders": "-- orders\nid INT"},
            query_result=QueryResult(columns=["id"], rows=[(1,)], row_count=1),
        )
        graph = build_text2sql_graph(sql_model, sql_engine, format_chat_model=format_model)
        # act
        result = graph.invoke({"question": "How many?"})  # pyright: ignore[reportUnknownMemberType]
        # assert — format model was invoked (its answer field is in the response)
        assert result["response"] == "One row."
        assert format_model.last_runnable.last_messages  # format model was called


class TestGraphTopology:
    """Verifies that all expected nodes are wired and reachable in the compiled graph."""

    def test_all_nodes_are_registered(self) -> None:
        """All seven pipeline nodes appear in the compiled graph."""
        # arrange / act
        graph = _make_graph()
        # assert — builder.nodes holds the spec dict keyed by node name
        registered = frozenset(graph.builder.nodes.keys())
        assert registered == _EXPECTED_NODES

    def test_non_conditional_edges_are_correct(self) -> None:
        """Deterministic edges match the expected linear pipeline structure."""
        # arrange / act
        graph = _make_graph()
        # assert — the execute_sql routing is a branch, not a deterministic edge
        edges = frozenset((src, dst) for src, dst in graph.builder.edges)
        assert edges == _EXPECTED_EDGES

    def test_execute_sql_has_conditional_branches(self) -> None:
        """execute_sql routes conditionally to repair_sql or format_response."""
        # arrange / act
        graph = _make_graph()
        # assert — routing targets are registered as branches from execute_sql
        branches = graph.builder.branches.get("execute_sql", {})
        assert branches  # at least one branch defined from execute_sql


class TestRepairLoop:
    """The repair loop retries SQL generation up to MAX_REPAIR_ATTEMPTS times."""

    def test_persistently_failing_sql_terminates_with_failure_message(self) -> None:
        """When all repair attempts fail the graph still returns a response."""
        # arrange — every execution errors, so repairs cannot recover
        chat_model = FakeStructuredChatModel(
            sql="SELECT bad FROM movies", answer="unused", tables=["movies"]
        )
        sql_engine = FakeSqlEngine(
            tables=["movies"],
            schemas={"movies": "-- movies\nDistributor VARCHAR"},
            error=ValueError("Binder Error: no such column bad"),
        )
        graph = build_text2sql_graph(chat_model, sql_engine)
        # act
        result = graph.invoke({"question": "How many films?"})  # pyright: ignore[reportUnknownMemberType]
        # assert — the loop is bounded (it returns) and degrades gracefully
        assert "couldn't" in str(result["response"]).lower()
        # initial execution + at least one repair re-execution occurred
        assert len(sql_engine.executed_sql) >= 3


class TestLayeringBoundary:
    """The production graph module must not depend on the eval harness."""

    def test_graph_module_does_not_import_eval(self) -> None:
        """text2sql_graph stays free of chat.infrastructure.eval imports (SoC)."""
        # arrange / act — inspect the module source for any eval coupling
        source = inspect.getsource(graph_module)
        # assert — eval instrumentation belongs in eval/, not the production builder
        assert "infrastructure.eval" not in source
