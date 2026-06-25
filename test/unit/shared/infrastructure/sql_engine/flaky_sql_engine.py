from shared.domain.value_objects.query_result import QueryResult


class FlakySqlEngine:
    """SqlEnginePort fake whose list_tables fails a fixed number of times first.

    Exercises node-level RetryPolicy: a transient error should be retried until
    it recovers, while a non-transient error (e.g. ValueError) should surface on
    the first attempt. ``list_tables_calls`` records how many times the node ran.
    """

    def __init__(
        self,
        tables: list[str],
        schema: str,
        query_result: QueryResult,
        error: Exception,
        fail_times: int,
    ) -> None:
        """Configure the result data plus how many leading calls raise ``error``."""
        self._tables = tables
        self._schema = schema
        self._query_result = query_result
        self._error = error
        self._fail_times = fail_times
        self.list_tables_calls = 0

    def list_tables(self) -> list[str]:
        """Raise ``error`` for the first ``fail_times`` calls, then return tables."""
        self.list_tables_calls += 1
        if self.list_tables_calls <= self._fail_times:
            raise self._error
        return self._tables

    def get_table_schema(self, table_name: str) -> str:
        """Return the single configured schema regardless of table name."""
        return self._schema

    def execute_query(self, sql: str) -> QueryResult:
        """Return the configured result set."""
        return self._query_result
