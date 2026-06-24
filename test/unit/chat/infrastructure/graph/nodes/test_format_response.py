from langchain_core.messages import SystemMessage

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.query_result import QueryResult
from chat.infrastructure.graph.nodes.format_response import FormatResponse
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)


def _state() -> ChatState:
    return ChatState(  # type: ignore[call-arg]
        question="How many orders?",
        sql_query="SELECT COUNT(*) FROM orders",
        query_result=QueryResult(columns=["count"], rows=[(42,)], row_count=1),
    )


class TestFormatResponse:
    def test_returns_answer_as_response(self) -> None:
        # arrange
        model = FakeStructuredChatModel(answer="There are 42 orders.")
        # act
        result = FormatResponse(model)(_state())
        # assert
        assert result == {"response": "There are 42 orders."}

    def test_sends_system_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(answer="42 orders.")
        # act
        FormatResponse(model)(_state())
        # assert
        messages = model.last_runnable.last_messages
        assert any(isinstance(m, SystemMessage) for m in messages)

    def test_includes_markdown_table_in_human_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(answer="42 orders.")
        # act
        FormatResponse(model)(_state())
        # assert
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "| count |" in combined
        assert "| 42 |" in combined

    def test_includes_question_in_human_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(answer="42 orders.")
        # act
        FormatResponse(model)(_state())
        # assert
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "How many orders?" in combined
