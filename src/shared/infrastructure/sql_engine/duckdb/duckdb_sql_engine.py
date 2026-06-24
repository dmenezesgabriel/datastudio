import re

import duckdb

from shared.domain.value_objects.query_result import QueryResult


class DuckDbSqlEngine:
    """DuckDB-backed implementation of SqlEnginePort.

    Example:
        engine = DuckDbSqlEngine("./dev_data/datastudio.duckdb")
        print(engine.list_tables())
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def list_tables(self) -> list[str]:
        with duckdb.connect(self._db_path, read_only=True) as conn:
            rows = conn.execute("SHOW TABLES").fetchall()
        return [row[0] for row in rows]

    def get_table_schema(self, table_name: str) -> str:
        self._validate_table_name(table_name)
        with duckdb.connect(self._db_path, read_only=True) as conn:
            rows = conn.execute(f"DESCRIBE {table_name}").fetchall()
        lines = [f"{row[0]} {row[1]}" for row in rows]
        return f"-- {table_name}\n" + "\n".join(lines)

    def execute_query(self, sql: str) -> QueryResult:
        with duckdb.connect(self._db_path, read_only=True) as conn:
            cursor = conn.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
        return QueryResult(columns=columns, rows=list(rows), row_count=len(rows))

    @staticmethod
    def _validate_table_name(table_name: str) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
            raise ValueError(
                f"Invalid table name {table_name!r}; expected pattern [A-Za-z_][A-Za-z0-9_]*"
            )
