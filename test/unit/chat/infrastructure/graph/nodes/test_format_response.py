from langchain_core.messages import SystemMessage

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.graph.nodes.format_response import FormatResponse
from shared.domain.value_objects.query_result import QueryResult
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


class TestFormatResponseHumanContent:
    def test_includes_row_count_for_single_row(self) -> None:
        # arrange — _state() returns row_count=1
        model = FakeStructuredChatModel(answer="42 orders.")
        # act
        FormatResponse(model)(_state())
        # assert
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "1 row" in combined

    def test_uses_plural_label_for_multiple_rows(self) -> None:
        # arrange
        model = FakeStructuredChatModel(answer="ans.")
        state = ChatState(  # type: ignore[call-arg]
            question="How many orders?",
            sql_query="SELECT COUNT(*) FROM orders",
            query_result=QueryResult(columns=["a", "b"], rows=[(1, 2), (3, 4)], row_count=2),
        )
        # act
        FormatResponse(model)(state)
        # assert
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "2 rows" in combined


class TestFormatResponseWithoutResult:
    def test_returns_failure_message_without_calling_model(self) -> None:
        # arrange — repair loop exhausted; no query_result in state
        model = FakeStructuredChatModel(answer="should not be used")
        state = ChatState(  # type: ignore[call-arg]
            question="How many orders?",
            sql_error="Binder Error: no such column",
        )
        # act
        result = FormatResponse(model)(state)
        # assert — a clear, honest message and no wasted LLM call
        assert "couldn't" in str(result["response"]).lower()
        assert model.last_runnable.last_messages == []
