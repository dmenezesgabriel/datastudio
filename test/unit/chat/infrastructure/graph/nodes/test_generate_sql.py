from langchain_core.messages import SystemMessage

from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes.generate_sql import GenerateSql
from test.unit.chat.infrastructure.graph.nodes.fake_malformed_chat_model import (
    FakeMalformedChatModel,
)
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
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
        assert result == {"sql": "SELECT COUNT(*) FROM orders"}

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


class TestGenerateSqlMalformedOutput:
    def test_returns_no_sql_instead_of_raising_on_malformed_output(self) -> None:
        # Regression: generate_sql called with_structured_output(...).invoke() raw, so
        # malformed structured output (ValidationError/OutputParserException) — which no
        # retry fixes — propagated out of the build_widget worker and failed the whole turn.
        # It must degrade to "no sql" so execute_sql records an error and the widget alone
        # falls back, not the entire turn.
        # arrange
        model = FakeMalformedChatModel()
        # act
        result = GenerateSql(model)(_state())
        # assert — no sql produced, and crucially no exception propagated
        assert result == {}


class TestGenerateSqlSystemPrompt:
    def test_instructs_excluding_nulls_from_rate_populations(self) -> None:
        # Regression: the model intermittently divided a rate by COUNT(*) including rows
        # whose measured column is NULL (unknown), counting "unknown" as failing the
        # condition and yielding a subtly wrong percentage. The prompt must require NULL
        # exclusion from both numerator and denominator.
        model = FakeStructuredChatModel(sql="SELECT 1")
        # act
        GenerateSql(model)(_state())
        # assert
        system = next(m for m in model.last_runnable.last_messages if isinstance(m, SystemMessage))
        text = str(system.content).lower()
        assert "null" in text
        assert "numerator" in text and "denominator" in text
