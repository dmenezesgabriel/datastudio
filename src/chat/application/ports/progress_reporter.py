"""Port for surfacing pipeline progress steps to the caller as they happen.

The thin, project-owned seam over whatever streaming mechanism the infrastructure
uses (LangGraph's custom stream writer in production). Nodes depend only on this
port, so progress reporting stays testable and free of graph internals.
"""

from typing import Protocol, runtime_checkable

from chat.domain.value_objects.stream_event import ProgressStep


@runtime_checkable
class ProgressReporter(Protocol):
    """Contract for emitting a progress step the moment it changes state.

    Example:
        reporter.report(ProgressStep("plan_widgets", "Planning the dashboard", "running"))
    """

    def report(self, step: ProgressStep) -> None:
        """Surface one progress step (running/done/failed) to the caller."""
        ...


class NullProgressReporter(ProgressReporter):
    """No-op reporter for paths without a live stream (CLI, unit tests).

    Example:
        BuildWidget(..., reporter=NullProgressReporter())  # progress simply dropped
    """

    def report(self, step: ProgressStep) -> None:
        """Discard the step; the memory-less/sync paths surface no live progress."""
