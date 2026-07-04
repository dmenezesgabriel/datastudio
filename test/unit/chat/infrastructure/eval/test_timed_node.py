"""Unit tests for TimedNode."""

from collections.abc import Mapping
from typing import cast

from chat.infrastructure.eval.metrics import EvalCollector
from chat.infrastructure.eval.timed_node import TimedNode
from chat.infrastructure.graph.chat_state import ChatState


def _inner(state: ChatState) -> Mapping[str, object]:
    return cast(Mapping[str, object], {})


class TestTimedNodeMetricsRecording:
    def test_latency_recorded_under_node_name(self) -> None:
        # arrange — kills __call____mutmut_5 (record_latency(None, ...) → key is None not name)
        recorder = EvalCollector()
        node = TimedNode("gen_sql", _inner, recorder)
        # act
        node(cast(ChatState, {}))
        # assert — latency must be stored under "gen_sql", not None
        assert "gen_sql" in recorder.node_metrics

    def test_latency_is_non_negative(self) -> None:
        # kills __call____mutmut_9 (perf_counter() + t0 gives ~2*timestamp, not ~0s elapsed)
        recorder = EvalCollector()
        node = TimedNode("gen_sql", _inner, recorder)
        # act
        node(cast(ChatState, {}))
        # assert — elapsed must be tiny (< 1 s for a no-op inner); + gives > 10**9
        assert recorder.node_metrics["gen_sql"].latency_s >= 0.0
        assert recorder.node_metrics["gen_sql"].latency_s < 1.0

    def test_set_node_called_with_node_name(self) -> None:
        # kills __init____mutmut_1 (self._name = None) and __call____mutmut_1 (set_node(None))
        recorder = EvalCollector()
        node = TimedNode("format_response", _inner, recorder)
        # act
        node(cast(ChatState, {}))
        # assert — current_node must be the name passed at construction
        assert recorder.current_node == "format_response"

    def test_inner_result_is_returned(self) -> None:
        # basic contract: result from inner must flow through unchanged
        def _returning_inner(state: ChatState) -> Mapping[str, object]:
            return cast(Mapping[str, object], {"answer": "42"})

        recorder = EvalCollector()
        node = TimedNode("n", _returning_inner, recorder)
        result = node(cast(ChatState, {}))
        assert result == {"answer": "42"}
