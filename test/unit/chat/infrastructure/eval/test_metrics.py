"""Unit tests for MetricsRecorder implementations."""

from chat.infrastructure.eval.metrics import EvalCollector, MetricsRecorder, NullMetricsRecorder


class TestNullMetricsRecorderProtocol:
    """NullMetricsRecorder satisfies MetricsRecorder and is a safe noop."""

    def test_satisfies_metrics_recorder_protocol(self) -> None:
        """Protocol check passes because MetricsRecorder is runtime_checkable."""
        assert isinstance(NullMetricsRecorder(), MetricsRecorder)

    def test_current_node_stays_empty_after_set_node(self) -> None:
        """set_node is a noop — current_node never changes."""
        # arrange
        recorder = NullMetricsRecorder()
        # act
        recorder.set_node("generate_sql")
        # assert — noop, no state change
        assert recorder.current_node == ""

    def test_record_latency_does_not_raise(self) -> None:
        """record_latency accepts args without error."""
        recorder = NullMetricsRecorder()
        recorder.record_latency("generate_sql", 1.5)

    def test_record_tokens_does_not_raise(self) -> None:
        """record_tokens accepts args without error."""
        recorder = NullMetricsRecorder()
        recorder.record_tokens("generate_sql", 100, 50)


class TestEvalCollectorProtocol:
    """EvalCollector satisfies MetricsRecorder."""

    def test_satisfies_metrics_recorder_protocol(self) -> None:
        """Protocol check passes because MetricsRecorder is runtime_checkable."""
        assert isinstance(EvalCollector(), MetricsRecorder)
