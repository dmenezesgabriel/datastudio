from shared.domain.value_objects.query_result import QueryResult
from shared.domain.value_objects.table_schema import ColumnDescriptor, TableSchema


class FakeSqlEngine:
    """In-memory SqlEnginePort implementation for testing."""

    def __init__(
        self,
        tables: list[str] | None = None,
        schemas: dict[str, str] | None = None,
        columns: dict[str, tuple[ColumnDescriptor, ...]] | None = None,
        query_result: QueryResult | None = None,
        results_by_sql: dict[str, QueryResult] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._tables = tables or []
        self._schemas = schemas or {}
        self._columns = columns or {}
        self.described_tables: list[str] = []
        self._query_result = query_result or QueryResult(columns=[], rows=[], row_count=0)
        self._results_by_sql = results_by_sql or {}
        self._error = error
        self.last_sql: str | None = None
        self.executed_sql: list[str] = []
        self.list_tables_calls = 0

    def list_tables(self) -> list[str]:
        self.list_tables_calls += 1
        return self._tables

    def get_table_schema(self, table_name: str) -> str:
        return self._schemas.get(table_name, f"-- {table_name}\n(no schema)")

    def describe_table(self, table_name: str) -> TableSchema:
        self.described_tables.append(table_name)
        return TableSchema(name=table_name, columns=self._columns.get(table_name, ()))

    def execute_query(self, sql: str) -> QueryResult:
        self.last_sql = sql
        self.executed_sql.append(sql)
        if sql in self._results_by_sql:
            return self._results_by_sql[sql]
        if self._error is not None:
            raise self._error
        return self._query_result
