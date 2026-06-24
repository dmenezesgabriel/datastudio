from langchain_core.messages import SystemMessage

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.nodes.generate_sql import GenerateSql
from test.unit.chat.infrastructure.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)


def _state() -> ChatState:
    return ChatState(schema="-- orders\nid INT", question="How many orders?")  # type: ignore[call-arg]


class TestGenerateSql:
    def test_returns_sql_from_structured_output(self) -> None:
        # arrange
        model = FakeStructuredChatModel(sql="SELECT COUNT(*) FROM orders")
        # act
        result = GenerateSql(model)(_state())
        # assert
        assert result == {"sql_query": "SELECT COUNT(*) FROM orders"}

    def test_sends_system_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(sql="SELECT 1")
        # act
        GenerateSql(model)(_state())
        # assert
        messages = model.last_runnable.last_messages
        assert any(isinstance(m, SystemMessage) for m in messages)

    def test_includes_schema_in_human_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(sql="SELECT 1")
        # act
        GenerateSql(model)(_state())
        # assert
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "orders" in combined

    def test_includes_question_in_human_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(sql="SELECT 1")
        # act
        GenerateSql(model)(_state())
        # assert
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "How many orders?" in combined
