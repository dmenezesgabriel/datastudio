"""Proxy node that brackets a graph node with running/done progress steps.

Mirrors the ``ObservableNode`` proxy pattern: wraps a ``TypedChatNode`` so the checklist gets a
``running`` step when the node starts and a ``done`` step when it returns, without the
node knowing about progress. Applied only to the sequential pipeline nodes — the
parallel ``build_widget`` workers report their own per-widget steps.
"""

from collections.abc import Mapping

from chat.application.ports.progress_reporter import ProgressReporter
from chat.domain.value_objects.stream_event import ProgressStep
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.types import TypedChatNode


class ProgressNode:
    """Wraps a node to report its step as running on entry and done on exit.

    Example:
        node = ProgressNode("get_schema", "Reading the schema", reporter, GetSchema(engine))
        node(state)  # reports get_schema running, runs the node, reports get_schema done
    """

    def __init__(
        self,
        step_id: str,
        label: str,
        reporter: ProgressReporter,
        inner: TypedChatNode,
    ) -> None:
        """Wire the step identity/copy, the reporter, and the inner node."""
        self._step_id = step_id
        self._label = label
        self._reporter = reporter
        self._inner = inner

    def __call__(self, state: ChatState) -> Mapping[str, object]:
        """Report running, delegate to the inner node, then report done."""
        self._reporter.report(ProgressStep(self._step_id, self._label, "running"))
        result = self._inner(state)
        self._reporter.report(ProgressStep(self._step_id, self._label, "done"))
        return result
