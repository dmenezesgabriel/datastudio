from langchain_core.messages import SystemMessage

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.sub_query_result import SubQueryResult
from chat.infrastructure.graph.nodes.synthesize_answer import SynthesizeAnswer
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)
from shared.domain.value_objects.query_result import QueryResult


def _sub(question: str, sql: str, value: float) -> SubQueryResult:
    return SubQueryResult(
        question=question,
        sql=sql,
        result=QueryResult(columns=["avg"], rows=[(value,)], row_count=1),
    )


def _state() -> ChatState:
    return ChatState(  # type: ignore[call-arg]
        question="By how many MPG did US cars improve between 1970 and 1980?",
        sub_results=[
            _sub(
                "Average MPG in 1970?",
                "SELECT AVG(mpg) FROM cars WHERE year = 1970",
                17.1,
            ),
            _sub(
                "Average MPG in 1980?",
                "SELECT AVG(mpg) FROM cars WHERE year = 1980",
                27.7,
            ),
        ],
    )


class TestSynthesizeAnswer:
    def test_returns_response_key(self) -> None:
        # arrange
        model = FakeStructuredChatModel(answer="Fuel efficiency improved by 10.6 MPG.")
        # act
        result = SynthesizeAnswer(model)(_state())
        # assert
        assert result == {"response": "Fuel efficiency improved by 10.6 MPG."}

    def test_sends_system_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(answer="Improved by 10.6 MPG.")
        # act
        SynthesizeAnswer(model)(_state())
        # assert
        messages = model.last_runnable.last_messages
        assert any(isinstance(m, SystemMessage) for m in messages)

    def test_includes_original_question_in_human_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(answer="Improved.")
        # act
        SynthesizeAnswer(model)(_state())
        # assert
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "1970" in combined
        assert "1980" in combined

    def test_includes_sub_result_tables_in_human_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(answer="Improved.")
        # act
        SynthesizeAnswer(model)(_state())
        # assert
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "17.1" in combined
        assert "27.7" in combined
