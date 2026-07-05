from types import SimpleNamespace
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr


class _FakeStructuredRunnable:
    """Captures invocation messages and returns a preconfigured response."""

    def __init__(self, **response_fields: Any) -> None:
        # Mirror _WidgetPlan's real defaults (kind="data", text_answer="") so plan doubles
        # are faithful without every call site restating them; explicit fields still win.
        # Other nodes read their own fields and ignore these extras.
        plan_defaults = {"kind": "data", "text_answer": ""}
        self._response = SimpleNamespace(**{**plan_defaults, **response_fields})
        self.last_messages: list[Any] = []

    def with_config(self, *args: Any, **kwargs: Any) -> "_FakeStructuredRunnable":
        """Honor the Runnable surface (tags/config are irrelevant to a fixed response)."""
        return self

    def invoke(self, messages: list[Any], *args: Any, **kwargs: Any) -> SimpleNamespace:
        self.last_messages = messages
        return self._response


class FakeStructuredChatModel(BaseChatModel):
    """Fake BaseChatModel for nodes that call with_structured_output.

    Inspect .last_runnable.last_messages to verify what the node sent.

    Usage:
        model = FakeStructuredChatModel(sql="SELECT 1")
        GenerateSql(model)(state)
        assert "SELECT 1" in model.last_runnable.last_messages[1].content
    """

    _last_runnable: _FakeStructuredRunnable = PrivateAttr()

    def __init__(self, **response_fields: Any) -> None:
        super().__init__()
        self._last_runnable = _FakeStructuredRunnable(**response_fields)

    @property
    def last_runnable(self) -> _FakeStructuredRunnable:
        return self._last_runnable

    def with_structured_output(self, schema: Any, **kwargs: Any) -> _FakeStructuredRunnable:
        return self._last_runnable

    def _generate(
        self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=""))])

    @property
    def _llm_type(self) -> str:
        return "fake-structured"
