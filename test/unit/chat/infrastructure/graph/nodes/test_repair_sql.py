from typing import cast

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.graph.nodes.repair_sql import MAX_REPAIR_ATTEMPTS, RepairSql
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.nodes.fake_sql_candidate_model import (
    FakeSqlCandidateModel,
)
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine


def _state(attempts: int = 0) -> ChatState:
    return cast(
        ChatState,
        {
            "question": "How many films?",
            "schema": "-- movies\nDistributor VARCHAR",
            "sql_query": "SELECT foo FROM movies",
            "sql_error": "Binder Error: no such column foo",
            "repair_attempts": attempts,
        },
    )


class TestRepairSqlNonFinalAttempt:
    def test_regenerates_sql_and_increments_attempts(self) -> None:
        # arrange
        model = FakeStructuredChatModel(sql="SELECT COUNT(*) FROM movies")
        engine = FakeSqlEngine()
        # act
        result = RepairSql(model, engine)(_state(attempts=0))
        # assert
        assert result == {
            "sql_query": "SELECT COUNT(*) FROM movies",
            "repair_attempts": 1,
        }

    def test_does_not_probe_engine_before_final_attempt(self) -> None:
        # arrange
        model = FakeStructuredChatModel(sql="SELECT 1")
        engine = FakeSqlEngine()
        # act
        RepairSql(model, engine)(_state(attempts=0))
        # assert — single-repair attempts let execute_sql re-run; no probing here
        assert engine.executed_sql == []

    def test_prompt_includes_previous_sql_and_error(self) -> None:
        # arrange
        model = FakeStructuredChatModel(sql="SELECT 1")
        # act
        RepairSql(model, FakeSqlEngine())(_state(attempts=0))
        # assert
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "SELECT foo FROM movies" in combined
        assert "Binder Error" in combined


class TestRepairSqlFinalAttempt:
    def test_picks_first_executable_candidate(self) -> None:
        # arrange — first candidate fails to execute, second succeeds
        good = QueryResult(columns=["c"], rows=[(318,)], row_count=1)
        model = FakeSqlCandidateModel(["BAD SQL", "GOOD SQL"])
        engine = FakeSqlEngine(results_by_sql={"GOOD SQL": good}, error=ValueError("bad"))
        # act — attempts=1 makes this the final (2nd) attempt
        result = RepairSql(model, engine, candidate_count=2)(_state(attempts=1))
        # assert
        assert result["sql_query"] == "GOOD SQL"
        assert result["repair_attempts"] == MAX_REPAIR_ATTEMPTS

    def test_falls_back_to_first_candidate_when_all_fail(self) -> None:
        # arrange — every candidate raises
        model = FakeSqlCandidateModel(["FIRST", "SECOND"])
        engine = FakeSqlEngine(error=ValueError("still broken"))
        # act
        result = RepairSql(model, engine, candidate_count=2)(_state(attempts=1))
        # assert
        assert result["sql_query"] == "FIRST"

    def test_stops_generating_after_first_successful_candidate(self) -> None:
        # arrange — first candidate executes cleanly; second must never be generated
        good = QueryResult(columns=["c"], rows=[(1,)], row_count=1)
        model = FakeSqlCandidateModel(["FIRST SQL", "SECOND SQL"])
        engine = FakeSqlEngine(results_by_sql={"FIRST SQL": good})
        # act
        RepairSql(model, engine, candidate_count=2)(_state(attempts=1))
        # assert — model called exactly once (early exit after first success)
        assert len(model.runnable.all_messages) == 1
