from chat.infrastructure.graph.nodes.execute_sql import ExecuteSql
from shared.domain.value_objects.query_result import QueryResult
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine


class TestExecuteSql:
    def test_returns_query_result_from_engine(self) -> None:
        # arrange
        expected = QueryResult(columns=["count"], rows=[(42,)], row_count=1)
        engine = FakeSqlEngine(query_result=expected)
        # act
        result = ExecuteSql(engine)({"sql_query": "SELECT COUNT(*) FROM t"})  # type: ignore[arg-type]
        # assert
        assert result == {"query_result": expected, "sql_error": ""}

    def test_passes_sql_query_from_state(self) -> None:
        # arrange
        engine = FakeSqlEngine()
        # act
        ExecuteSql(engine)({"sql_query": "SELECT 1"})  # type: ignore[arg-type]
        # assert
        assert engine.last_sql == "SELECT 1"


class TestExecuteSqlErrorCapture:
    def test_captures_error_message_without_query_result(self) -> None:
        # arrange — engine raises on every query
        engine = FakeSqlEngine(error=ValueError("Binder Error: no such column foo"))
        # act
        result = ExecuteSql(engine)({"sql_query": "SELECT foo FROM t"})  # type: ignore[arg-type]
        # assert — the error is surfaced for the repair loop, no result is set
        assert "query_result" not in result
        assert "Binder Error" in str(result["sql_error"])

    def test_does_not_raise_on_failure(self) -> None:
        # arrange
        engine = FakeSqlEngine(error=RuntimeError("boom"))
        # act / assert — failure is captured, not propagated
        ExecuteSql(engine)({"sql_query": "SELECT 1"})  # type: ignore[arg-type]
