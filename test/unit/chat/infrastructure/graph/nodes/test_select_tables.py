import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import SystemMessage

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.graph.nodes.select_tables import SelectTables
from test.unit.chat.infrastructure.graph.nodes.fake_failing_chat_model import (
    FailingStructuredChatModel,
)
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)


def _state(
    tables: list[str] | None = None,
    question: str = "How many films has Warner Bros. released?",
) -> ChatState:
    return ChatState(tables=tables or ["movies", "cars", "nyc_taxi"], question=question)  # type: ignore[call-arg]


class TestSelectTables:
    def test_returns_filtered_tables_from_structured_output(self) -> None:
        # arrange
        model = FakeStructuredChatModel(tables=["movies"])
        # act
        result = SelectTables(model)(_state())
        # assert
        assert result == {"tables": ["movies"]}

    def test_sends_system_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(tables=["movies"])
        # act
        SelectTables(model)(_state())
        # assert
        messages = model.last_runnable.last_messages
        assert any(isinstance(m, SystemMessage) for m in messages)

    def test_includes_table_names_in_human_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(tables=["movies"])
        # act
        SelectTables(model)(_state(tables=["movies", "cars"]))
        # assert
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "movies" in combined
        assert "cars" in combined

    def test_includes_question_in_human_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(tables=["movies"])
        # act
        SelectTables(model)(_state())
        # assert
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "Warner Bros." in combined

    def test_falls_back_to_all_tables_when_model_returns_unknown_name(self) -> None:
        # arrange — model hallucinates a table name not in the available list
        model = FakeStructuredChatModel(tables=["nonexistent_table"])
        state = _state(tables=["movies", "cars"])
        # act
        result = SelectTables(model)(state)
        # assert — fallback to full original table list
        assert result == {"tables": ["movies", "cars"]}


class TestSelectTablesResilience:
    def test_malformed_output_keeps_all_tables(self) -> None:
        # arrange — structured output can't be parsed (deterministic failure)
        model = FailingStructuredChatModel(OutputParserException("no tool call"))
        # act
        result = SelectTables(model)(_state(tables=["movies", "cars"]))
        # assert — safe superset so get_schema still runs, no crash
        assert result == {"tables": ["movies", "cars"]}

    def test_transient_error_propagates_to_retry_policy(self) -> None:
        # arrange — a transient error must NOT be swallowed (RetryPolicy handles it)
        model = FailingStructuredChatModel(ConnectionError("blip"))
        # act / assert
        with pytest.raises(ConnectionError):
            SelectTables(model)(_state())
