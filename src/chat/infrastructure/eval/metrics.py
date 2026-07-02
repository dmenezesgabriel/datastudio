"""Per-node execution metrics for the eval pipeline."""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@runtime_checkable
class MetricsRecorder(Protocol):
    """Narrow interface for recording per-node execution metrics.

    Consumers (TimedNode, TokenCountingCallback) depend on this abstraction
    rather than the concrete EvalCollector.

    Example:
        recorder: MetricsRecorder = EvalCollector()
        recorder.set_node("generate_sql")
        recorder.record_latency("generate_sql", 1.23)
    """

    current_node: str

    def set_node(self, name: str) -> None:
        """Mark the currently executing node (used for token attribution)."""
        ...

    def record_latency(self, node: str, elapsed: float) -> None:
        """Record wall-clock execution time for a node in seconds."""
        ...

    def record_tokens(self, node: str, input_t: int, output_t: int, cached_t: int = 0) -> None:
        """Record LLM token usage attributed to a node (cached_t: prompt-cache reads)."""
        ...


@dataclass
class NodeMetrics:
    """Accumulated metrics for a single node execution.

    ``cached_input_tokens`` is the prompt-prefix portion the provider served from cache —
    a subset of ``input_tokens``, tracked so effective/fresh input cost stays visible.
    """

    latency_s: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None


class NullMetricsRecorder:
    """No-op MetricsRecorder for production graphs that don't need instrumentation.

    Satisfies the MetricsRecorder protocol so TimedNode and TokenCountingCallback
    can be used uniformly in both production and eval builds.

    Example:
        graph = build_eval_graph(llm, engine, NullMetricsRecorder())
    """

    current_node: str = ""

    def set_node(self, name: str) -> None:
        """No-op implementation."""

    def record_latency(self, node: str, elapsed: float) -> None:
        """No-op implementation."""

    def record_tokens(self, node: str, input_t: int, output_t: int, cached_t: int = 0) -> None:
        """No-op implementation."""


@dataclass
class EvalCollector:
    """Mutable accumulator for one graph run. Implements MetricsRecorder.

    Example:
        collector = EvalCollector()
        collector.set_node("generate_sql")
        collector.record_latency("generate_sql", 1.23)
        collector.record_tokens("generate_sql", 450, 32)
        collector.node_metrics["generate_sql"]  # NodeMetrics(latency_s=1.23, ...)
    """

    current_node: str = ""
    node_metrics: dict[str, NodeMetrics] = field(default_factory=dict[str, NodeMetrics])

    def set_node(self, name: str) -> None:
        """Set current_node and initialise a NodeMetrics entry if absent."""
        self.current_node = name
        if name not in self.node_metrics:
            self.node_metrics[name] = NodeMetrics()

    def record_latency(self, node: str, elapsed: float) -> None:
        """Store elapsed seconds for the given node."""
        if node not in self.node_metrics:
            self.node_metrics[node] = NodeMetrics()
        self.node_metrics[node].latency_s = elapsed

    def record_tokens(self, node: str, input_t: int, output_t: int, cached_t: int = 0) -> None:
        """Accumulate token counts for the given node (cached_t: prompt-cache reads)."""
        if node not in self.node_metrics:
            self.node_metrics[node] = NodeMetrics()
        metrics = self.node_metrics[node]
        metrics.input_tokens = (metrics.input_tokens or 0) + input_t
        metrics.output_tokens = (metrics.output_tokens or 0) + output_t
        metrics.cached_input_tokens = (metrics.cached_input_tokens or 0) + cached_t
