"""DuckDB implementation of the SQL engine port."""

import re

import duckdb
from duckdb import DuckDBPyConnection

from shared.domain.value_objects.query_result import QueryResult

# A column qualifies as a low-cardinality category (worth showing example values
# for) when it has at most this many distinct non-null values.
_LOW_CARDINALITY_MAX = 20
_SAMPLE_VALUES_SHOWN = 3


class DuckDbSqlEngine:
    """DuckDB-backed implementation of SqlEnginePort.

    Schemas are returned as DDL annotated with NOT NULL markers and, for
    low-cardinality text columns, a few example values — this lets the model
    match literal filters (e.g. origin = 'USA') instead of guessing.

    Example:
        engine = DuckDbSqlEngine("./dev_data/datastudio.duckdb")
        print(engine.list_tables())
    """

    def __init__(self, db_path: str) -> None:
        """Store the DuckDB file path."""
        self._db_path = db_path

    def list_tables(self) -> list[str]:
        """Query SHOW TABLES and return table names as a list."""
        with duckdb.connect(self._db_path, read_only=True) as conn:
            rows = conn.execute("SHOW TABLES").fetchall()
        return [row[0] for row in rows]

    def get_table_schema(self, table_name: str) -> str:
        """Return annotated DDL for the table with example values for text columns."""
        self._validate_table_name(table_name)
        with duckdb.connect(self._db_path, read_only=True) as conn:
            rows = conn.execute(f'DESCRIBE "{table_name}"').fetchall()
            lines = [self._describe_column(conn, table_name, row) for row in rows]
        return f"-- {table_name}\n" + "\n".join(lines)

    def execute_query(self, sql: str) -> QueryResult:
        """Execute a SQL query and return the result as a QueryResult."""
        with duckdb.connect(self._db_path, read_only=True) as conn:
            cursor = conn.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
        return QueryResult(columns=columns, rows=list(rows), row_count=len(rows))

    def _describe_column(
        self, conn: DuckDBPyConnection, table: str, row: tuple[object, ...]
    ) -> str:
        name, col_type = str(row[0]), str(row[1])
        nullable = "" if str(row[2]).upper() == "YES" else " NOT NULL"
        examples = self._sample_values(conn, table, name, col_type)
        suffix = f"  -- e.g. {examples}" if examples else ""
        return f"{name} {col_type}{nullable}{suffix}"

    def _sample_values(
        self, conn: DuckDBPyConnection, table: str, column: str, col_type: str
    ) -> str:
        """Return a few example values for low-cardinality text columns, else ''.

        Best-effort and bounded: the LIMIT short-circuits high-cardinality
        columns, and any probe failure degrades to no examples rather than
        breaking schema retrieval — so one slow/unsupported column never blocks
        the rest (matters at warehouse scale).
        """
        if not self._is_textual(col_type):
            return ""
        col, tbl = self._quote(column), self._quote(table)
        # Identifiers are quoted/escaped via _quote and the limit is a constant;
        # DuckDB has no bound-parameter form for identifiers, so f-string
        # construction is required and safe here (no user-controlled input).
        query = (
            f"SELECT DISTINCT {col} FROM {tbl} "  # nosec B608
            f"WHERE {col} IS NOT NULL LIMIT {_LOW_CARDINALITY_MAX + 1}"
        )
        try:
            rows = conn.execute(query).fetchall()
        except Exception:  # noqa: BLE001 — value sampling is best-effort, never fatal
            return ""
        if not rows or len(rows) > _LOW_CARDINALITY_MAX:
            return ""
        return ", ".join(str(r[0]) for r in rows[:_SAMPLE_VALUES_SHOWN])

    @staticmethod
    def _is_textual(col_type: str) -> bool:
        upper = col_type.upper()
        return "CHAR" in upper or upper in ("TEXT", "STRING")

    @staticmethod
    def _quote(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    @staticmethod
    def _validate_table_name(table_name: str) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
            raise ValueError(
                f"Invalid table name {table_name!r}; expected pattern [A-Za-z_][A-Za-z0-9_]*"
            )
