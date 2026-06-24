import pytest
import duckdb

from chat.infrastructure.duckdb_sql_engine import DuckDbSqlEngine


@pytest.fixture()
def db_path(tmp_path: pytest.TempPathFactory) -> str:
    path = str(tmp_path / "test.duckdb")
    with duckdb.connect(path) as conn:
        conn.execute("CREATE TABLE items (id INTEGER, label VARCHAR)")
        conn.execute("INSERT INTO items VALUES (1, 'alpha'), (2, 'beta')")
    return path


class TestDuckDbSqlEngine:
    def test_list_tables_returns_table_names(self, db_path: str) -> None:
        engine = DuckDbSqlEngine(db_path)
        assert engine.list_tables() == ["items"]

    def test_get_table_schema_includes_column_names(self, db_path: str) -> None:
        schema = DuckDbSqlEngine(db_path).get_table_schema("items")
        assert "id" in schema
        assert "label" in schema

    def test_get_table_schema_prefixes_table_name(self, db_path: str) -> None:
        schema = DuckDbSqlEngine(db_path).get_table_schema("items")
        assert schema.startswith("-- items")

    def test_get_table_schema_rejects_invalid_name(self, db_path: str) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            DuckDbSqlEngine(db_path).get_table_schema("bad; DROP TABLE items")

    def test_execute_query_returns_correct_columns(self, db_path: str) -> None:
        result = DuckDbSqlEngine(db_path).execute_query("SELECT id, label FROM items")
        assert result.columns == ["id", "label"]

    def test_execute_query_returns_correct_rows(self, db_path: str) -> None:
        result = DuckDbSqlEngine(db_path).execute_query("SELECT id FROM items ORDER BY id")
        assert result.rows == [(1,), (2,)]

    def test_execute_query_row_count_matches(self, db_path: str) -> None:
        result = DuckDbSqlEngine(db_path).execute_query("SELECT * FROM items")
        assert result.row_count == 2
