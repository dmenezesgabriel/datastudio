from typing import Any

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr


class _MalformedRunnable:
    """A structured-output runnable whose invoke always raises malformed output.

    Models the deterministic failure ``with_structured_output`` throws when the provider
    returns text that cannot be coerced into the target schema — the exact class the
    graph must degrade around rather than crash the whole turn on.
    """

    def __init__(self) -> None:
        self.last_messages: list[Any] = []

    def with_config(self, *args: Any, **kwargs: Any) -> "_MalformedRunnable":
        return self

    def invoke(self, messages: list[Any], *args: Any, **kwargs: Any) -> Any:
        self.last_messages = messages
        raise OutputParserException("could not parse structured output")


class FakeMalformedChatModel(BaseChatModel):
    """Fake chat model whose structured-output runnable always raises malformed output.

    Usage:
        model = FakeMalformedChatModel()
        result = GenerateSql(model)(state)  # returns {} instead of raising
    """

    _runnable: _MalformedRunnable = PrivateAttr()

    def __init__(self) -> None:
        super().__init__()
        self._runnable = _MalformedRunnable()

    @property
    def runnable(self) -> _MalformedRunnable:
        return self._runnable

    def with_structured_output(self, schema: Any, **kwargs: Any) -> _MalformedRunnable:
        return self._runnable

    def _generate(
        self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=""))])

    @property
    def _llm_type(self) -> str:
        return "fake-malformed"
