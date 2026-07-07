"""Tests for the route_intent gate node."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from langchain_core.exceptions import OutputParserException

from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes.route_intent import RouteIntent
from test.unit.chat.infrastructure.graph.nodes.fake_failing_chat_model import (
    FailingStructuredChatModel,
)


class FakeIntentModel:
    """Returns a canned intent decision and records the messages it answered."""

    def __init__(self, kind: str = "data", reply: str = "") -> None:
        self._decision = SimpleNamespace(kind=kind, reply=reply)
        self.received: list[Any] = []

    def with_structured_output(self, schema: Any, **kwargs: Any) -> "FakeIntentModel":
        return self

    def invoke(self, messages: list[Any]) -> SimpleNamespace:
        self.received = messages
        return self._decision


def _node(kind: str = "data", reply: str = "") -> RouteIntent:
    return RouteIntent(cast(Any, FakeIntentModel(kind=kind, reply=reply)))


def _state(question: str = "q", history: list[Any] | None = None) -> ChatState:
    # No schema key: the gate must classify from question + history alone.
    return cast(ChatState, {"question": question, "history": history or []})


class TestRouteIntentChitchat:
    def test_chitchat_short_circuits_to_a_trimmed_text_answer(self) -> None:
        # arrange — the gate confidently classifies a greeting as chitchat
        node = _node(kind="chitchat", reply="  Hi! Ask me about your data.  ")
        # act
        out = node(_state(question="hello"))
        # assert — a direct text answer, promoted later by answer_text; no pipeline entry
        assert out == {"answer_kind": "text", "text_answer": "Hi! Ask me about your data."}


class TestRouteIntentDataFallthrough:
    def test_data_kind_returns_empty_so_the_pipeline_runs(self) -> None:
        out = _node(kind="data")(_state(question="revenue by month"))
        assert out == {}

    def test_chitchat_without_reply_falls_through_to_data(self) -> None:
        # kind says chitchat but there is no content to answer with — never emit a blank.
        out = _node(kind="chitchat", reply="   ")(_state(question="hi"))
        assert out == {}


class TestRouteIntentPrompt:
    def test_sends_question_and_history_but_no_schema(self) -> None:
        from langchain_core.messages import AIMessage, HumanMessage

        model = FakeIntentModel(kind="data")
        history = [HumanMessage(content="prior q"), AIMessage(content="prior a")]
        RouteIntent(cast(Any, model))(_state(question="now", history=history))
        # [System, *history, Human(current)] in order — prior turns as short-term memory
        assert [type(m).__name__ for m in model.received] == [
            "SystemMessage",
            "HumanMessage",
            "AIMessage",
            "HumanMessage",
        ]
        assert model.received[1].content == "prior q"
        assert model.received[-1].content == "now"
        # the gate never sees the schema (that is the whole point — no DB before routing)
        assert all("schema" not in str(m.content).lower() for m in model.received[1:])


class TestRouteIntentResilience:
    def test_malformed_output_falls_through_to_data(self) -> None:
        # malformed structured output must not swallow a real question as chitchat
        node = RouteIntent(FailingStructuredChatModel(OutputParserException("bad")))
        assert node(_state(question="revenue?")) == {}

    def test_transient_error_propagates_to_retry_policy(self) -> None:
        node = RouteIntent(FailingStructuredChatModel(ConnectionError("blip")))
        with pytest.raises(ConnectionError):
            node(_state())
