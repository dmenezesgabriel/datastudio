from chat.domain.value_objects.query_result import QueryResult


class FakeSqlEngine:
    """In-memory SqlEnginePort implementation for testing."""

    def __init__(
        self,
        tables: list[str] | None = None,
        schemas: dict[str, str] | None = None,
        query_result: QueryResult | None = None,
    ) -> None:
        self._tables = tables or []
        self._schemas = schemas or {}
        self._query_result = query_result or QueryResult(
            columns=[], rows=[], row_count=0
        )
        self.last_sql: str | None = None

    def list_tables(self) -> list[str]:
        return self._tables

    def get_table_schema(self, table_name: str) -> str:
        return self._schemas.get(table_name, f"-- {table_name}\n(no schema)")

    def execute_query(self, sql: str) -> QueryResult:
        self.last_sql = sql
        return self._query_result
