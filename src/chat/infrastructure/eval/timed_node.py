from collections.abc import Mapping
from time import perf_counter
from typing import Protocol

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.eval.metrics import MetricsRecorder


class _ChatNode(Protocol):
    def __call__(self, state: ChatState) -> Mapping[str, object]: ...


class TimedNode:
    """Wraps a graph node callable with wall-clock timing and current-node tracking.

    Records latency to the MetricsRecorder and sets current_node before calling the
    inner node so that TokenCountingCallback can attribute LLM tokens correctly.

    Example:
        recorder = EvalCollector()
        node = TimedNode("generate_sql", GenerateSql(model), recorder)
        result = node(state)  # latency recorded, current_node set during inner call
    """

    def __init__(self, name: str, inner: _ChatNode, recorder: MetricsRecorder) -> None:
        self._name = name
        self._inner = inner
        self._recorder = recorder

    def __call__(self, state: ChatState) -> Mapping[str, object]:
        self._recorder.set_node(self._name)
        t0 = perf_counter()
        result = self._inner(state)
        self._recorder.record_latency(self._name, perf_counter() - t0)
        return result
