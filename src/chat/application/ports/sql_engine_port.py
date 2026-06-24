from typing import Protocol, runtime_checkable

from chat.domain.value_objects.query_result import QueryResult


@runtime_checkable
class SqlEnginePort(Protocol):
    """Contract for SQL execution backends.

    Example:
        engine: SqlEnginePort = DuckDbSqlEngine("./data.duckdb")
        tables = engine.list_tables()
        schema = engine.get_table_schema("orders")
        result = engine.execute_query("SELECT COUNT(*) FROM orders")
    """

    def list_tables(self) -> list[str]: ...

    def get_table_schema(self, table_name: str) -> str: ...

    def execute_query(self, sql: str) -> QueryResult: ...
