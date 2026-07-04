"""Tests for the compose_narrative node (overall dashboard summary)."""

from typing import cast

import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage

from chat.domain.value_objects.widget import WidgetResult
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes.compose_narrative import ComposeNarrative
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.nodes.fake_failing_chat_model import (
    FailingStructuredChatModel,
)
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)


def _widget(widget_id: str, title: str, value: int) -> WidgetResult:
    return WidgetResult(
        widget_id=widget_id,
        title=title,
        result=QueryResult(columns=["n"], rows=[(value,)], row_count=1),
        sql="SELECT 1",
    )


def _state(
    question: str,
    widget_results: list[WidgetResult],
    history: list[BaseMessage] | None = None,
) -> ChatState:
    return cast(
        ChatState,
        {"question": question, "widget_results": widget_results, "history": history or []},
    )


class TestComposeNarrative:
    def test_summarizes_via_structured_output(self) -> None:
        model = FakeStructuredChatModel(answer="Revenue is strong across categories.")
        state = _state("overview", [_widget("widget-0", "Revenue", 42)])
        assert ComposeNarrative(model)(state) == {
            "narrative": "Revenue is strong across categories."
        }

    def test_prompt_includes_each_widget_title_and_rows(self) -> None:
        model = FakeStructuredChatModel(answer="ok")
        state = _state(
            "sales overview",
            [_widget("widget-0", "Total revenue", 1000), _widget("widget-1", "Orders", 50)],
        )
        ComposeNarrative(model)(state)
        human = str(model.last_runnable.last_messages[-1].content)
        assert "Total revenue" in human and "Orders" in human
        assert "1000" in human and "50" in human  # the result values are shown to the summarizer

    def test_no_results_returns_failure_message(self) -> None:
        model = FakeStructuredChatModel(answer="unused")
        state = _state("q", [])
        response = ComposeNarrative(model)(state)["narrative"]
        assert "couldn't" in response.lower()


class TestComposeNarrativeResilience:
    def test_malformed_output_falls_back_to_titled_summary(self) -> None:
        # arrange — the summary model returns malformed output, but widgets DID run
        model = FailingStructuredChatModel(OutputParserException("bad"))
        state = _state(
            "overview",
            [_widget("widget-0", "Total revenue", 1000), _widget("widget-1", "Orders", 50)],
        )
        # act
        response = ComposeNarrative(model)(state)["narrative"]
        # assert — a deterministic sentence naming the widgets, not a crash
        assert "Total revenue" in response and "Orders" in response

    def test_transient_error_propagates_to_retry_policy(self) -> None:
        model = FailingStructuredChatModel(ConnectionError("blip"))
        state = _state("q", [_widget("widget-0", "Revenue", 42)])
        with pytest.raises(ConnectionError):
            ComposeNarrative(model)(state)
