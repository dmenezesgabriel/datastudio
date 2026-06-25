"""Unit tests for build_eval_graph (instrumented text2sql graph for eval runs)."""

from chat.infrastructure.eval.graph_builder import build_eval_graph
from chat.infrastructure.eval.metrics import EvalCollector
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine


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
        chat_model = FakeStructuredChatModel(sql="SELECT 1", answer="One row.", tables=["orders"])
        graph = build_eval_graph(chat_model, _make_engine(), recorder)
        # act
        graph.invoke({"question": "How many?"})  # pyright: ignore[reportUnknownMemberType]
        # assert — at least some nodes recorded latency
        assert recorder.node_metrics, "expected at least one timed node"
        assert any(m.latency_s >= 0.0 for m in recorder.node_metrics.values())

    def test_behaviour_matches_production_graph(self) -> None:
        """Instrumentation does not change the produced response."""
        # arrange
        recorder = EvalCollector()
        chat_model = FakeStructuredChatModel(sql="SELECT 1", answer="One row.", tables=["orders"])
        graph = build_eval_graph(chat_model, _make_engine(), recorder)
        # act
        result = graph.invoke({"question": "How many?"})  # pyright: ignore[reportUnknownMemberType]
        # assert
        assert result["response"] == "One row."
