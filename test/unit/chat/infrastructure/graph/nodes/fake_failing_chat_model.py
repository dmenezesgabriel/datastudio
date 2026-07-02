from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr


class _RaisingRunnable:
    """Structured-output runnable that always raises a preset exception on invoke."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def with_config(self, *args: Any, **kwargs: Any) -> "_RaisingRunnable":
        return self

    def invoke(self, messages: list[Any], *args: Any, **kwargs: Any) -> Any:
        raise self._error


class FailingStructuredChatModel(BaseChatModel):
    """Fake whose structured output always raises — malformed output or a transient error.

    Use to prove a node falls back on malformed output yet still propagates transient
    errors to the graph RetryPolicy.

    Usage:
        model = FailingStructuredChatModel(OutputParserException("bad"))
        SelectTables(model)(state)  # returns fallback, does not raise
    """

    _error: Exception = PrivateAttr()

    def __init__(self, error: Exception) -> None:
        super().__init__()
        self._error = error

    def with_structured_output(self, schema: Any, **kwargs: Any) -> _RaisingRunnable:
        return _RaisingRunnable(self._error)

    def _generate(
        self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=""))])

    @property
    def _llm_type(self) -> str:
        return "failing-structured"
