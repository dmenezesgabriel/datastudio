from langchain_core.messages import SystemMessage

from chat.domain.value_objects.query_result import QueryResult
from chat.infrastructure.nodes.format_response import FormatResponse
from test.unit.chat.infrastructure.nodes.fake_structured_chat_model import FakeStructuredChatModel


def _state() -> dict:  # type: ignore[type-arg]
    return {
        "question": "How many orders?",
        "sql_query": "SELECT COUNT(*) FROM orders",
        "query_result": QueryResult(columns=["count"], rows=[(42,)], row_count=1),
    }


class TestFormatResponse:
    def test_returns_answer_as_response(self) -> None:
        model = FakeStructuredChatModel(answer="There are 42 orders.")
        result = FormatResponse(model)(_state())  # type: ignore[arg-type]
        assert result == {"response": "There are 42 orders."}

    def test_sends_system_message(self) -> None:
        model = FakeStructuredChatModel(answer="42 orders.")
        FormatResponse(model)(_state())  # type: ignore[arg-type]
        messages = model.last_runnable.last_messages
        assert any(isinstance(m, SystemMessage) for m in messages)

    def test_includes_markdown_table_in_human_message(self) -> None:
        model = FakeStructuredChatModel(answer="42 orders.")
        FormatResponse(model)(_state())  # type: ignore[arg-type]
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "| count |" in combined
        assert "| 42 |" in combined

    def test_includes_question_in_human_message(self) -> None:
        model = FakeStructuredChatModel(answer="42 orders.")
        FormatResponse(model)(_state())  # type: ignore[arg-type]
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "How many orders?" in combined
