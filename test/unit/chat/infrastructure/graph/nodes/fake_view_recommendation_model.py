from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

from chat.domain.value_objects.view_spec import ViewSpec


class _FakeViewRunnable:
    """Captures invocation messages and returns a preconfigured ViewSpec."""

    def __init__(self, view_spec: ViewSpec) -> None:
        self._view_spec = view_spec
        self.last_messages: list[Any] = []

    def invoke(self, messages: list[Any]) -> ViewSpec:
        self.last_messages = messages
        return self._view_spec


class FakeViewRecommendationModel(BaseChatModel):
    """Fake BaseChatModel for RecommendView; returns a fixed ViewSpec.

    Inspect .last_runnable.last_messages to verify what the node sent (empty when
    the node short-circuits without calling the model).
    """

    _runnable: _FakeViewRunnable = PrivateAttr()

    def __init__(self, view_spec: ViewSpec) -> None:
        super().__init__()
        self._runnable = _FakeViewRunnable(view_spec)

    @property
    def last_runnable(self) -> _FakeViewRunnable:
        return self._runnable

    def with_structured_output(self, schema: Any, **kwargs: Any) -> _FakeViewRunnable:
        return self._runnable

    def _generate(
        self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=""))])

    @property
    def _llm_type(self) -> str:
        return "fake-view"
