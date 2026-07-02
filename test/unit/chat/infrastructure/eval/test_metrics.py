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


class TestEvalCollectorRecordTokens:
    """record_tokens accumulates input, output, and cached-input counts per node."""

    def test_records_cached_input_tokens(self) -> None:
        # arrange
        collector = EvalCollector()
        # act
        collector.record_tokens("generate_widget_view", 604, 20, cached_t=581)
        # assert
        metrics = collector.node_metrics["generate_widget_view"]
        assert metrics.input_tokens == 604
        assert metrics.output_tokens == 20
        assert metrics.cached_input_tokens == 581

    def test_cached_defaults_to_zero_when_omitted(self) -> None:
        # arrange
        collector = EvalCollector()
        # act — existing callers pass no cached_t
        collector.record_tokens("generate_sql", 100, 50)
        # assert — cached stays at 0, not None, once a call has landed
        assert collector.node_metrics["generate_sql"].cached_input_tokens == 0

    def test_accumulates_cached_across_calls(self) -> None:
        # arrange
        collector = EvalCollector()
        # act — two LLM calls attribute to the same node
        collector.record_tokens("repair_sql", 100, 10, cached_t=80)
        collector.record_tokens("repair_sql", 120, 12, cached_t=90)
        # assert
        assert collector.node_metrics["repair_sql"].cached_input_tokens == 170
