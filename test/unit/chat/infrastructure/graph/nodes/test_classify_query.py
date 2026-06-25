from langchain_core.messages import SystemMessage

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.graph.nodes.classify_query import ClassifyQuery
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)


def _state(question: str = "How many films has Warner Bros. released?") -> ChatState:
    return ChatState(question=question)  # type: ignore[call-arg]


class TestClassifyQuery:
    def test_returns_simple_complexity(self) -> None:
        # arrange
        model = FakeStructuredChatModel(complexity="simple")
        # act
        result = ClassifyQuery(model)(_state())
        # assert
        assert result == {"complexity": "simple"}

    def test_returns_complex_complexity(self) -> None:
        # arrange
        model = FakeStructuredChatModel(complexity="complex")
        # act
        result = ClassifyQuery(model)(
            _state("By how many MPG did US cars improve between 1970 and 1980?")
        )
        # assert
        assert result == {"complexity": "complex"}

    def test_sends_system_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(complexity="simple")
        # act
        ClassifyQuery(model)(_state())
        # assert
        messages = model.last_runnable.last_messages
        assert any(isinstance(m, SystemMessage) for m in messages)

    def test_includes_question_in_human_message(self) -> None:
        # arrange
        model = FakeStructuredChatModel(complexity="simple")
        question = "How many films has Warner Bros. released?"
        # act
        ClassifyQuery(model)(_state(question))
        # assert
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert question in combined
