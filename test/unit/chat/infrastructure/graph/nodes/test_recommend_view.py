from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.view_spec import KpiSpec, ViewSpec
from chat.infrastructure.graph.nodes.recommend_view import RecommendView
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.nodes.fake_view_recommendation_model import (
    FakeViewRecommendationModel,
)


def _spec() -> ViewSpec:
    return ViewSpec(
        kpis=[KpiSpec(label="Total", value_column="revenue")], charts=[], show_table=True
    )


def _state_with_result() -> ChatState:
    return ChatState(  # type: ignore[call-arg]
        question="Revenue by month?",
        query_result=QueryResult(columns=["month", "revenue"], rows=[("Jan", 100)], row_count=1),
    )


class TestRecommendView:
    def test_returns_view_spec_when_result_present(self) -> None:
        # arrange
        spec = _spec()
        model = FakeViewRecommendationModel(spec)
        # act
        result = RecommendView(model)(_state_with_result())
        # assert
        assert result == {"view_spec": spec}

    def test_prompt_includes_columns_and_sample(self) -> None:
        # arrange
        model = FakeViewRecommendationModel(_spec())
        # act
        RecommendView(model)(_state_with_result())
        # assert
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "revenue" in combined
        assert "Jan" in combined

    def test_prompt_includes_question(self) -> None:
        # arrange — kills __call____mutmut_13 (_build_human_content(None, ...) loses question)
        model = FakeViewRecommendationModel(_spec())
        # act
        RecommendView(model)(_state_with_result())
        # assert — "Revenue by month?" must appear in the message
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "Revenue by month?" in combined


class TestRecommendViewWithoutResult:
    def test_returns_empty_without_calling_model(self) -> None:
        # arrange — repair loop exhausted; no query_result
        model = FakeViewRecommendationModel(_spec())
        state = ChatState(question="x", sql_error="boom")  # type: ignore[call-arg]
        # act
        result = RecommendView(model)(state)
        # assert — nothing to visualize, and no wasted LLM call
        assert result == {}
        assert model.last_runnable.last_messages == []
