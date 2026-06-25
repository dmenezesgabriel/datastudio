from typing import cast

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.eval.checks import ExecutionMatchCheck, deserialize_check
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine

_GOLD_SQL = "SELECT COUNT(*) FROM movies WHERE Distributor = 'Warner Bros.'"


def _engine(gold: QueryResult) -> FakeSqlEngine:
    return FakeSqlEngine(results_by_sql={_GOLD_SQL: gold})


def _state_with_result(result: QueryResult) -> ChatState:
    return cast(ChatState, {"question": "How many films?", "query_result": result})


class TestExecutionMatchCheckScalar:
    def test_passes_when_candidate_matches_gold(self) -> None:
        # arrange — gold and candidate both return 318
        gold = QueryResult(columns=["c"], rows=[(318,)], row_count=1)
        candidate = QueryResult(columns=["count"], rows=[(318,)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act
        result = check.evaluate(_state_with_result(candidate))
        # assert
        assert result["passed"] is True

    def test_fails_when_values_differ(self) -> None:
        # arrange
        gold = QueryResult(columns=["c"], rows=[(318,)], row_count=1)
        candidate = QueryResult(columns=["count"], rows=[(999,)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act
        result = check.evaluate(_state_with_result(candidate))
        # assert
        assert result["passed"] is False

    def test_tolerates_float_precision(self) -> None:
        # arrange — gold rounds, candidate is unrounded
        gold = QueryResult(columns=["avg"], rows=[(6.77,)], row_count=1)
        candidate = QueryResult(columns=["avg"], rows=[(6.7741,)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act
        result = check.evaluate(_state_with_result(candidate))
        # assert
        assert result["passed"] is True

    def test_tolerates_summation_noise_on_unrounded_large_floats(self) -> None:
        # arrange — two executions of a large SUM differ in the lowest digits
        gold = QueryResult(columns=["s"], rows=[(145047454.13116914,)], row_count=1)
        candidate = QueryResult(columns=["s"], rows=[(145047454.13116920,)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act / assert
        assert check.evaluate(_state_with_result(candidate))["passed"] is True

    def test_rejects_fraction_vs_percentage(self) -> None:
        # arrange — a 100x unit error must still fail (0.0063 fraction vs 0.63 percent)
        gold = QueryResult(columns=["pct"], rows=[(0.63,)], row_count=1)
        candidate = QueryResult(columns=["pct"], rows=[(0.0063,)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act / assert
        assert check.evaluate(_state_with_result(candidate))["passed"] is False


class TestExecutionMatchCheckRowSets:
    def test_passes_order_insensitive(self) -> None:
        # arrange — same rows, different order
        gold = QueryResult(columns=["s"], rows=[("SP",), ("RJ",)], row_count=2)
        candidate = QueryResult(columns=["s"], rows=[("RJ",), ("SP",)], row_count=2)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act / assert
        assert check.evaluate(_state_with_result(candidate))["passed"] is True

    def test_fails_when_row_counts_differ(self) -> None:
        # arrange — candidate dumps the whole column; gold expects one row
        gold = QueryResult(columns=["s"], rows=[("SP",)], row_count=1)
        candidate = QueryResult(columns=["s"], rows=[("SP",), ("RJ",), ("MG",)], row_count=3)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act / assert
        assert check.evaluate(_state_with_result(candidate))["passed"] is False

    def test_passes_when_candidate_has_extra_descriptive_column(self) -> None:
        # arrange — gold names the state; candidate also returns the count
        gold = QueryResult(columns=["state"], rows=[("SP",)], row_count=1)
        candidate = QueryResult(columns=["state", "n"], rows=[("SP", 11000)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act / assert — every gold value is present in the candidate row
        assert check.evaluate(_state_with_result(candidate))["passed"] is True


class TestExecutionMatchCheckMissingResult:
    def test_fails_without_query_result(self) -> None:
        # arrange
        gold = QueryResult(columns=["c"], rows=[(1,)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act
        result = check.evaluate(cast(ChatState, {"question": "q"}))
        # assert
        assert result["passed"] is False
        assert "no query result" in result["reasoning"]


class TestDeserializeExecutionMatch:
    def test_builds_execution_match_check_with_engine(self) -> None:
        # arrange
        engine = FakeSqlEngine()
        judge = FakeStructuredChatModel(passed=True, reasoning="")
        spec = {"type": "execution_match", "gold_sql": _GOLD_SQL}
        # act
        check = deserialize_check(spec, judge, engine)
        # assert
        assert isinstance(check, ExecutionMatchCheck)
        assert check.gold_sql == _GOLD_SQL
