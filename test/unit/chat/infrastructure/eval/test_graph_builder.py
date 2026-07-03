"""Unit tests for build_eval_graph (instrumented text2sql graph for eval runs)."""

from types import SimpleNamespace

from chat.infrastructure.eval.graph_builder import build_eval_graph
from chat.infrastructure.eval.metrics import EvalCollector
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine

_WIDGETS = [SimpleNamespace(title="Count", sub_question="how many orders")]


def _make_engine() -> FakeSqlEngine:
    """Engine that lists one table and returns a single-row result."""
    return FakeSqlEngine(
        tables=["orders"],
        schemas={"orders": "-- orders\nid INT"},
        query_result=QueryResult(columns=["id"], rows=[(1,)], row_count=1),
    )


class TestBuildEvalGraph:
    """build_eval_graph wraps every node in TimedNode and records per-node metrics."""

    def test_records_node_latencies(self) -> None:
        """Node metrics are populated in the recorder after graph invocation."""
        # arrange
        recorder = EvalCollector()
        chat_model = FakeStructuredChatModel(
            sql="SELECT 1", answer="One row.", tables=["orders"], widgets=_WIDGETS
        )
        graph = build_eval_graph(chat_model, _make_engine(), recorder)
        # act
        graph.invoke({"question": "How many?", "history": []})  # pyright: ignore[reportUnknownMemberType]
        # assert — at least some nodes recorded latency
        assert recorder.node_metrics, "expected at least one timed node"
        assert any(m.latency_s >= 0.0 for m in recorder.node_metrics.values())

    def test_behaviour_matches_production_graph(self) -> None:
        """Instrumentation does not change the produced response."""
        # arrange
        recorder = EvalCollector()
        chat_model = FakeStructuredChatModel(
            sql="SELECT 1", answer="One row.", tables=["orders"], widgets=_WIDGETS
        )
        graph = build_eval_graph(chat_model, _make_engine(), recorder)
        # act
        result = graph.invoke({"question": "How many?", "history": []})  # pyright: ignore[reportUnknownMemberType]
        # assert
        assert result["response"] == "One row."

    def test_node_metrics_keys_are_string_node_names(self) -> None:
        # kills mutmut_9 (TimedNode(None, ...) makes recorder.node_metrics[None] the key)
        recorder = EvalCollector()
        chat_model = FakeStructuredChatModel(
            sql="SELECT 1", answer="One row.", tables=["orders"], widgets=_WIDGETS
        )
        graph = build_eval_graph(chat_model, _make_engine(), recorder)
        # act
        graph.invoke({"question": "How many?", "history": []})  # pyright: ignore[reportUnknownMemberType]
        # assert — every key must be a string (not None)
        assert all(isinstance(k, str) for k in recorder.node_metrics), recorder.node_metrics
        assert None not in recorder.node_metrics

    def test_format_chat_model_is_used_for_response(self) -> None:
        # kills mutmut_4 (format_chat_model=None always) and mutmut_7 (missing kwarg)
        # arrange — format_chat_model gives a distinct answer from chat_model
        sql_model = FakeStructuredChatModel(
            sql="SELECT 1", answer="SQL answer", tables=["orders"], widgets=_WIDGETS
        )
        fmt_model = FakeStructuredChatModel(
            sql="SELECT 1", answer="Format answer", tables=["orders"], widgets=_WIDGETS
        )
        graph = build_eval_graph(
            sql_model, _make_engine(), EvalCollector(), format_chat_model=fmt_model
        )
        # act
        result = graph.invoke({"question": "How many?", "history": []})  # pyright: ignore[reportUnknownMemberType]
        # assert — format_chat_model's answer must be used, not sql_model's
        assert result["response"] == "Format answer"
