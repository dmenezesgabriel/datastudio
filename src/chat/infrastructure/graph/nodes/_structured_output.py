"""Invoke a structured-output runnable, isolating malformed output from transient errors.

``with_structured_output`` can fail two ways with very different remedies: a transient
provider error (connection blip, 5xx) that the graph's ``RetryPolicy`` should retry, or
malformed/empty output that no retry will fix. This helper swallows *only* the latter —
returning ``None`` so the caller can fall back deterministically — and lets every other
exception propagate, so transient failures still reach the RetryPolicy. Keeping this in one
place stops the three discovery/narrative nodes from each re-deriving that distinction.
"""

from collections.abc import Sequence

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from pydantic import ValidationError

from shared.infrastructure.logging.logger_factory import get_logger

_logger = get_logger(__name__)

# Malformed structured output is deterministic, so the fix is a fallback, not a retry.
_MALFORMED_OUTPUT = (OutputParserException, ValidationError)


def invoke_structured[T](
    runnable: Runnable[LanguageModelInput, T], messages: Sequence[BaseMessage], step: str
) -> T | None:
    """Invoke a structured-output runnable; return None on malformed output.

    Args:
        runnable: The ``with_structured_output`` runnable to invoke.
        messages: The prompt messages to send.
        step: Node name, used only to label the warning log for observability.

    Example:
        plan = invoke_structured(self._model, messages, "plan_widgets")
        if plan is None:
            return {"widget_specs": [_fallback_widget(question)]}
    """
    try:
        return runnable.invoke(messages)
    except _MALFORMED_OUTPUT as exc:
        _logger.warning(
            "structured_output.malformed",
            extra={"step": step, "error": type(exc).__name__},
        )
        return None
