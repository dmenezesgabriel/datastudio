from chat.domain.value_objects.query_result import QueryResult
from chat.infrastructure.nodes.execute_sql import ExecuteSql
from test.unit.chat.infrastructure.nodes.fake_sql_engine import FakeSqlEngine


class TestExecuteSql:
    def test_returns_query_result_from_engine(self) -> None:
        expected = QueryResult(columns=["count"], rows=[(42,)], row_count=1)
        engine = FakeSqlEngine(query_result=expected)
        result = ExecuteSql(engine)({"sql_query": "SELECT COUNT(*) FROM t"})  # type: ignore[arg-type]
        assert result == {"query_result": expected}

    def test_passes_sql_query_from_state(self) -> None:
        engine = FakeSqlEngine()
        ExecuteSql(engine)({"sql_query": "SELECT 1"})  # type: ignore[arg-type]
        assert engine.last_sql == "SELECT 1"
