from typing import cast

from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes.repair_sql import (
    _CANDIDATE_HINTS,
    MAX_REPAIR_ATTEMPTS,
    RepairSql,
)
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


class TestRepairSqlInit:
    def test_default_candidate_count_is_three(self) -> None:
        # arrange — create with defaults, then verify via _hints()
        model = FakeStructuredChatModel(sql="SELECT 1")
        node = RepairSql(model, FakeSqlEngine())
        # act / assert — default candidate_count=3 → 3 hints
        assert len(node._hints()) == 3

    def test_custom_candidate_count_limits_hints(self) -> None:
        model = FakeStructuredChatModel(sql="SELECT 1")
        node = RepairSql(model, FakeSqlEngine(), candidate_count=2)
        assert len(node._hints()) == 2


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

    def test_prompt_includes_candidate_hint(self) -> None:
        # arrange — first hint must appear in the prompt to guide the model
        model = FakeStructuredChatModel(sql="SELECT 1")
        # act
        RepairSql(model, FakeSqlEngine())(_state(attempts=0))
        # assert — _CANDIDATE_HINTS[0] content must be in the message
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "direct correction" in combined.lower()

    def test_prompt_includes_schema(self) -> None:
        # arrange — schema must reach the model (kills _build_messages mutmut_7/9/11/12)
        model = FakeStructuredChatModel(sql="SELECT 1")
        # act
        RepairSql(model, FakeSqlEngine())(_state(attempts=0))
        # assert — "Distributor VARCHAR" comes from _state()'s schema
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "Distributor VARCHAR" in combined

    def test_prompt_includes_question(self) -> None:
        # arrange — question must reach the model (kills _build_messages mutmut_14/16/18/19)
        model = FakeStructuredChatModel(sql="SELECT 1")
        # act
        RepairSql(model, FakeSqlEngine())(_state(attempts=0))
        # assert — "How many films?" comes from _state()'s question
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "How many films?" in combined


class TestRepairSqlBuildMessagesDefaults:
    """Verify that missing state keys produce empty strings, not None or 'XXXX'."""

    def _combined(self, state: ChatState) -> str:
        messages = RepairSql._build_messages(state, "hint")
        return " ".join(str(m.content) for m in messages)

    def test_missing_schema_produces_empty_not_none(self) -> None:
        # kills mutmut_8 (default=None), mutmut_10 (no default), mutmut_13 (default='XXXX')
        state = cast(ChatState, {"question": "q", "sql_query": "SELECT 1", "sql_error": "err"})
        combined = self._combined(state)
        assert "Schema:\nNone" not in combined
        assert "Schema:\nXXXX" not in combined

    def test_missing_question_produces_empty_not_none(self) -> None:
        # kills mutmut_15 (default=None), mutmut_17 (no default), mutmut_20 (default='XXXX')
        state = cast(ChatState, {"schema": "-- t", "sql_query": "SELECT 1", "sql_error": "err"})
        combined = self._combined(state)
        assert "Question: None" not in combined
        assert "Question: XXXX" not in combined

    def test_missing_sql_query_produces_empty_not_none(self) -> None:
        # kills mutmut_22 (default=None), mutmut_24 (no default), mutmut_27 (default='XXXX')
        state = cast(ChatState, {"schema": "-- t", "question": "q", "sql_error": "err"})
        combined = self._combined(state)
        assert "Previous SQL:\nNone" not in combined
        assert "Previous SQL:\nXXXX" not in combined

    def test_missing_sql_error_produces_empty_not_none(self) -> None:
        # kills mutmut_29 (default=None), mutmut_31 (no default), mutmut_34 (default='XXXX')
        state = cast(ChatState, {"schema": "-- t", "question": "q", "sql_query": "SELECT 1"})
        combined = self._combined(state)
        assert "Error: None" not in combined
        assert "Error: XXXX" not in combined


class TestRepairSqlCurrentAttempts:
    def test_returns_zero_when_repair_attempts_key_missing(self) -> None:
        # arrange — state without repair_attempts; else branch must return 0 not 1
        state = cast(ChatState, {})
        # act / assert — kills _current_attempts__mutmut_9 (else 1 instead of 0)
        assert RepairSql._current_attempts(state) == 0


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

    def test_best_candidate_passes_hint_to_each_call(self) -> None:
        # arrange — _CANDIDATE_HINTS[0] must appear in the message sent to the model
        # kills _best_candidate__mutmut_4 (passes hint=None instead of hint)
        good = QueryResult(columns=["c"], rows=[(1,)], row_count=1)
        model = FakeSqlCandidateModel(["GOOD SQL"])
        engine = FakeSqlEngine(results_by_sql={"GOOD SQL": good})
        # act — candidate_count=1 → only first hint used
        RepairSql(model, engine, candidate_count=1)(_state(attempts=1))
        # assert — hint text must be in the first (and only) model call
        messages = model.runnable.all_messages[0]
        combined = " ".join(str(m.content) for m in messages)
        assert _CANDIDATE_HINTS[0].lower() in combined.lower()

    def test_falls_back_to_empty_string_when_first_candidate_sql_is_empty(self) -> None:
        # arrange — model returns empty SQL; all candidates fail to execute
        # kills _best_candidate__mutmut_11 (first or "XXXX" instead of first or "")
        model = FakeSqlCandidateModel([""])
        engine = FakeSqlEngine(error=ValueError("still broken"))
        # act — candidate_count=1, attempts=1 (final attempt)
        result = RepairSql(model, engine, candidate_count=1)(_state(attempts=1))
        # assert — fallback must be "" not "XXXX"
        assert result["sql_query"] == ""
