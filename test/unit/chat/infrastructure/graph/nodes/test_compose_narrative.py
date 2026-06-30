"""Tests for the compose_narrative node (overall dashboard summary)."""

from typing import cast

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.widget import WidgetResult
from chat.infrastructure.graph.nodes.compose_narrative import ComposeNarrative
from shared.domain.value_objects.query_result import QueryResult
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


class TestComposeNarrative:
    def test_summarizes_via_structured_output(self) -> None:
        model = FakeStructuredChatModel(answer="Revenue is strong across categories.")
        state = cast(
            ChatState,
            {"question": "overview", "widget_results": [_widget("widget-0", "Revenue", 42)]},
        )
        assert ComposeNarrative(model)(state) == {
            "response": "Revenue is strong across categories."
        }

    def test_prompt_includes_each_widget_title_and_rows(self) -> None:
        model = FakeStructuredChatModel(answer="ok")
        state = cast(
            ChatState,
            {
                "question": "sales overview",
                "widget_results": [
                    _widget("widget-0", "Total revenue", 1000),
                    _widget("widget-1", "Orders", 50),
                ],
            },
        )
        ComposeNarrative(model)(state)
        human = str(model.last_runnable.last_messages[-1].content)
        assert "Total revenue" in human and "Orders" in human
        assert "1000" in human and "50" in human  # the result values are shown to the summarizer

    def test_no_results_returns_failure_message(self) -> None:
        model = FakeStructuredChatModel(answer="unused")
        state = cast(ChatState, {"question": "q", "widget_results": []})
        response = ComposeNarrative(model)(state)["response"]
        assert "couldn't" in response.lower()
