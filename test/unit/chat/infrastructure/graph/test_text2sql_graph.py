"""Unit tests for build_text2sql_graph and wire_text2sql_graph (orchestrator–workers)."""

import inspect
from types import SimpleNamespace
from typing import cast

from langgraph.graph.state import CompiledStateGraph  # pyright: ignore[reportMissingTypeStubs]
from langgraph.types import Send

from chat.domain.value_objects.widget import WidgetSpec
from chat.infrastructure.graph import text2sql_graph as graph_module
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.text2sql_graph import build_text2sql_graph, fan_out_widgets
from chat.infrastructure.graph.types import TypedChatGraph
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine

_EXPECTED_NODES = frozenset(
    {
        "route_intent",
        "list_tables",
        "select_tables",
        "get_schema",
        "plan_widgets",
        "build_widget",
        "answer_text",
        "compose_narrative",
    }
)
_EXPECTED_EDGES = frozenset(
    {
        ("__start__", "route_intent"),
        # route_intent → list_tables / answer_text is a conditional route, not a static edge
        ("list_tables", "select_tables"),
        ("select_tables", "get_schema"),
        ("get_schema", "plan_widgets"),
        # plan_widgets → build_widget / answer_text is a conditional route, not a static edge
        ("build_widget", "compose_narrative"),
        ("answer_text", "__end__"),
        ("compose_narrative", "__end__"),
    }
)


def _widget(title: str, sub_question: str, role: str = "analysis") -> SimpleNamespace:
    return SimpleNamespace(title=title, sub_question=sub_question, role=role)


def _make_graph(widgets: list[SimpleNamespace] | None = None) -> TypedChatGraph:
    chat_model = FakeStructuredChatModel(
        tables=["orders"],
        widgets=widgets or [_widget("Count", "how many orders")],
        sql="SELECT 1",
        answer="One row.",
    )
    sql_engine = FakeSqlEngine(
        tables=["orders"],
        schemas={"orders": "-- orders\nid INT"},
        query_result=QueryResult(columns=["id"], rows=[(1,)], row_count=1),
    )
    return build_text2sql_graph(chat_model, sql_engine)


class TestBuildText2SqlGraph:
    def test_returns_compiled_state_graph(self) -> None:
        assert isinstance(_make_graph(), CompiledStateGraph)

    def test_invoke_returns_overall_narrative(self) -> None:
        result = _make_graph().invoke({"question": "How many?", "history": []})  # pyright: ignore[reportUnknownMemberType]
        assert result["narrative"] == "One row."

    def test_invoke_aggregates_results_from_parallel_widgets(self) -> None:
        # two planned widgets → two build_widget workers → two aggregated results
        graph = _make_graph([_widget("A", "qa"), _widget("B", "qb")])
        result = graph.invoke({"question": "overview", "history": []})  # pyright: ignore[reportUnknownMemberType]
        assert len(result["widget_results"]) == 2
        assert {w.widget_id for w in result["widget_results"]} == {"widget-0", "widget-1"}
        # each widget contributed view patch lines to the shared reducer channel
        assert result["widget_patch_lines"]


class TestChitchatGate:
    def test_chitchat_short_circuits_before_any_schema_discovery(self) -> None:
        # arrange — route_intent classifies the turn as chitchat and drafts a reply
        chat_model = FakeStructuredChatModel(
            tables=["orders"],
            kind="chitchat",
            reply="Hi! Ask me about your data.",
            widgets=[],
            sql="",
            answer="unused",
        )
        sql_engine = FakeSqlEngine(
            tables=["orders"],
            schemas={"orders": "-- orders\nid INT"},
            query_result=QueryResult(columns=["id"], rows=[(1,)], row_count=1),
        )
        # act
        result = build_text2sql_graph(chat_model, sql_engine).invoke(  # pyright: ignore[reportUnknownMemberType]
            {"question": "hello", "history": []}
        )
        # assert — the gate's reply is the response, and the data pipeline never ran:
        # no table listing (so no select_tables/get_schema/plan_widgets) and no SQL/widgets
        assert result["narrative"] == "Hi! Ask me about your data."
        assert not result.get("widget_results")
        assert sql_engine.list_tables_calls == 0
        assert sql_engine.executed_sql == []


class TestTextBranch:
    def test_text_kind_answers_without_running_widgets(self) -> None:
        # arrange — the planner classifies the turn as text (a meta/greeting question)
        chat_model = FakeStructuredChatModel(
            tables=["orders"],
            kind="text",
            text_answer="I can query and visualize your data.",
            widgets=[],
            sql="",
            answer="unused",
        )
        sql_engine = FakeSqlEngine(
            tables=["orders"],
            schemas={"orders": "-- orders\nid INT"},
            query_result=QueryResult(columns=["id"], rows=[(1,)], row_count=1),
        )
        # act
        result = build_text2sql_graph(chat_model, sql_engine).invoke(  # pyright: ignore[reportUnknownMemberType]
            {"question": "what can you do?", "history": []}
        )
        # assert — the drafted answer is the response, and no widget worker ran
        assert result["narrative"] == "I can query and visualize your data."
        assert not result.get("widget_results")


class TestFanOut:
    def test_emits_one_send_per_widget_with_shared_context(self) -> None:
        specs = [
            WidgetSpec(id="widget-0", title="A", sub_question="qa", role="metric"),
            WidgetSpec(id="widget-1", title="B", sub_question="qb", role="analysis"),
        ]
        state = cast(ChatState, {"widget_specs": specs, "schema": "-- s", "tables": ["orders"]})
        sends = fan_out_widgets(state)
        assert all(isinstance(s, Send) and s.node == "build_widget" for s in sends)
        assert [s.arg["widget"].id for s in sends] == ["widget-0", "widget-1"]
        assert sends[0].arg["schema"] == "-- s" and sends[0].arg["tables"] == ["orders"]

    def test_no_widgets_emits_no_sends(self) -> None:
        assert fan_out_widgets(cast(ChatState, {"widget_specs": []})) == []


class TestGraphTopology:
    def test_all_nodes_are_registered(self) -> None:
        assert frozenset(_make_graph().builder.nodes.keys()) == _EXPECTED_NODES

    def test_static_edges_are_correct(self) -> None:
        edges = frozenset((src, dst) for src, dst in _make_graph().builder.edges)
        assert edges == _EXPECTED_EDGES

    def test_plan_widgets_has_conditional_fan_out(self) -> None:
        assert _make_graph().builder.branches.get("plan_widgets")

    def test_route_intent_is_the_entry_and_branches(self) -> None:
        # the gate runs first (START → route_intent) and conditionally routes the turn
        assert _make_graph().builder.branches.get("route_intent")


class TestFailurePath:
    def test_persistent_sql_failure_still_returns_a_response(self) -> None:
        # every execution errors → no widget_results → compose_narrative degrades gracefully
        chat_model = FakeStructuredChatModel(
            tables=["movies"], widgets=[_widget("X", "q")], sql="SELECT bad", answer="unused"
        )
        sql_engine = FakeSqlEngine(
            tables=["movies"], schemas={"movies": "-- movies"}, error=ValueError("Binder Error")
        )
        graph = build_text2sql_graph(chat_model, sql_engine)
        result = graph.invoke({"question": "q", "history": []})  # pyright: ignore[reportUnknownMemberType]
        assert "couldn't" in str(result["narrative"]).lower()


class TestLayeringBoundary:
    def test_graph_module_does_not_import_eval(self) -> None:
        source = inspect.getsource(graph_module)
        assert "infrastructure.eval" not in source
