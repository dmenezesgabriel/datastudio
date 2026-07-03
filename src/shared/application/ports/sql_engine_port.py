"""Port interface for SQL execution backends."""

from typing import Protocol, runtime_checkable

from shared.domain.value_objects.query_result import QueryResult


@runtime_checkable
class SqlEnginePort(Protocol):
    """Contract for SQL execution backends.

    Scales by backend: the graph never fetches every schema — select_tables
    prunes first, so get_table_schema is only called for the handful of tables
    a question needs. For warehouse backends with many tables (e.g. AWS Athena),
    implementations should source the schema (and any sample values it embeds)
    from catalog metadata / statistics or a cached profile rather than scanning
    data per call, so cost and latency stay bounded as table count grows.

    Example:
        engine: SqlEnginePort = DuckDbSqlEngine("./data.duckdb")
        tables = engine.list_tables()
        schema = engine.get_table_schema("events")
        result = engine.execute_query("SELECT COUNT(*) FROM events")
    """

    def list_tables(self) -> list[str]:
        """Return the names of all tables in the database."""
        ...

    def get_table_schema(self, table_name: str) -> str:
        """Return a DDL-style schema string annotated with column info for the given table."""
        ...

    def execute_query(self, sql: str) -> QueryResult:
        """Execute a SQL SELECT and return the result set."""
        ...
