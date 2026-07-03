"""ProgressReporter backed by LangGraph's custom stream writer.

Wraps ``langgraph.config.get_stream_writer`` (per CLAUDE.md: third-party libs sit
behind a thin project interface) so nodes emit ``ProgressStep``s that surface on the
graph's ``stream_mode="custom"`` channel. Resolves the writer lazily at report time,
so a single instance works across every node invocation of a run.
"""

from langgraph.config import get_stream_writer

from chat.application.ports.progress_reporter import ProgressReporter
from chat.domain.value_objects.stream_event import ProgressStep


class StreamWriterProgressReporter(ProgressReporter):
    """Pushes each ProgressStep onto the active graph's custom stream.

    Outside a streaming graph run (the CLI ``invoke`` path, or a node exercised
    directly in a unit test) there is no writer to resolve, so ``report`` is a safe
    no-op — progress is optional telemetry, never load-bearing.

    Example:
        reporter = StreamWriterProgressReporter()
        reporter.report(ProgressStep("get_schema", "Reading the schema", "running"))
    """

    def report(self, step: ProgressStep) -> None:
        """Emit the step on the custom channel; no-op when no stream is active."""
        try:
            writer = get_stream_writer()
        except RuntimeError:
            return  # called outside a runnable context (direct unit-test call)
        writer(step)  # default writer is a no-op lambda on the sync/CLI path
