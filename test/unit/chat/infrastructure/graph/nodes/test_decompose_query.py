from langchain_core.messages import SystemMessage

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.sub_query_result import SubQueryResult
from chat.infrastructure.graph.nodes.decompose_query import DecomposeQuery
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine
from shared.domain.value_objects.query_result import QueryResult


def _state(
    question: str = "By how many MPG did US cars improve between 1970 and 1980?",
) -> ChatState:
    return ChatState(  # type: ignore[call-arg]
        question=question,
        schema="-- cars\nMiles_per_Gallon FLOAT\nYear DATE\nOrigin VARCHAR",
    )


def _engine(sql_result: QueryResult | None = None) -> FakeSqlEngine:
    return FakeSqlEngine(
        query_result=sql_result
        or QueryResult(columns=["avg"], rows=[(17.0,)], row_count=1)
    )


class TestDecomposeQuery:
    def test_returns_sub_results_list(self) -> None:
        # arrange — model returns two sub-questions
        model = FakeStructuredChatModel(
            sub_questions=[
                "Average MPG for US cars in 1970?",
                "Average MPG for US cars in 1980?",
            ],
            sql="SELECT AVG(Miles_per_Gallon) FROM cars WHERE Origin = 'USA'",
        )
        engine = _engine()
        # act
        result = DecomposeQuery(model, engine)(_state())
        # assert
        assert "sub_results" in result
        assert len(result["sub_results"]) == 2

    def test_each_sub_result_has_question_sql_and_result(self) -> None:
        # arrange
        model = FakeStructuredChatModel(
            sub_questions=["Average MPG in 1970?"],
            sql="SELECT AVG(Miles_per_Gallon) FROM cars WHERE year = 1970",
        )
        engine = _engine(QueryResult(columns=["avg"], rows=[(17.1,)], row_count=1))
        # act
        result = DecomposeQuery(model, engine)(_state())
        # assert
        sub: SubQueryResult = result["sub_results"][0]
        assert sub.question == "Average MPG in 1970?"
        assert isinstance(sub.sql, str)
        assert isinstance(sub.result, QueryResult)

    def test_sends_system_message_for_decomposition(self) -> None:
        # arrange
        model = FakeStructuredChatModel(sub_questions=["q1?"], sql="SELECT 1")
        # act
        DecomposeQuery(model, _engine())(_state())
        # assert
        messages = model.last_runnable.last_messages
        assert any(isinstance(m, SystemMessage) for m in messages)

    def test_includes_schema_in_llm_messages(self) -> None:
        # arrange — schema contains "Miles_per_Gallon"; GenerateSql receives it too
        model = FakeStructuredChatModel(sub_questions=["q1?"], sql="SELECT 1")
        # act
        DecomposeQuery(model, _engine())(_state())
        # assert — schema content appears in at least one model call's messages
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "cars" in combined

    def test_executes_sql_via_engine(self) -> None:
        # arrange
        model = FakeStructuredChatModel(
            sub_questions=["Average MPG in 1970?"], sql="SELECT AVG(m) FROM cars"
        )
        engine = _engine()
        # act
        DecomposeQuery(model, engine)(_state())
        # assert — engine received the generated SQL
        assert engine.last_sql == "SELECT AVG(m) FROM cars"
