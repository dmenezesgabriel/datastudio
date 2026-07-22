import duckdb
import pytest

from shared.infrastructure.sql_engine.duckdb.duckdb_sql_engine import (
    DuckDbSqlEngine,
)


@pytest.fixture()
def db_path(tmp_path: pytest.TempPathFactory) -> str:
    path = str(tmp_path / "test.duckdb")
    with duckdb.connect(path) as conn:
        conn.execute("CREATE TABLE items (id INTEGER, label VARCHAR)")
        conn.execute("INSERT INTO items VALUES (1, 'alpha'), (2, 'beta')")
    return path


class TestIsTextual:
    def test_varchar_is_textual(self) -> None:
        assert DuckDbSqlEngine._is_textual("VARCHAR") is True

    def test_text_is_textual(self) -> None:
        assert DuckDbSqlEngine._is_textual("TEXT") is True

    def test_string_is_textual(self) -> None:
        assert DuckDbSqlEngine._is_textual("STRING") is True

    def test_integer_is_not_textual(self) -> None:
        assert DuckDbSqlEngine._is_textual("INTEGER") is False

    def test_double_is_not_textual(self) -> None:
        assert DuckDbSqlEngine._is_textual("DOUBLE") is False


class TestQuote:
    def test_wraps_identifier_in_double_quotes(self) -> None:
        assert DuckDbSqlEngine._quote("table_name") == '"table_name"'

    def test_escapes_embedded_double_quote(self) -> None:
        # identifier containing " must become "" inside the quoted identifier
        assert DuckDbSqlEngine._quote('col"name') == '"col""name"'


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

    def test_execute_query_row_count_matches_len_of_rows(self, db_path: str) -> None:
        # distinguishes row_count=len(rows) from other mutations
        result = DuckDbSqlEngine(db_path).execute_query("SELECT id FROM items")
        assert result.row_count == len(result.rows)

    def test_get_table_schema_joins_columns_without_extra_separator(self, db_path: str) -> None:
        # arrange — schema with two columns must not have extra separators
        schema = DuckDbSqlEngine(db_path).get_table_schema("items")
        lines = schema.split("\n")
        # first line is "-- items", subsequent lines are column definitions
        assert lines[0] == "-- items"
        assert len(lines) == 3  # header + id + label

    def test_get_table_schema_marks_not_null_columns(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        # arrange — a table with an explicit NOT NULL column
        path = str(tmp_path / "notnull.duckdb")  # type: ignore[operator]
        with duckdb.connect(path) as conn:
            conn.execute("CREATE TABLE t (x INTEGER NOT NULL)")
        schema = DuckDbSqlEngine(path).get_table_schema("t")
        assert "NOT NULL" in schema

    def test_list_tables_returns_correct_count(self, db_path: str) -> None:
        tables = DuckDbSqlEngine(db_path).list_tables()
        assert isinstance(tables, list)
        assert len(tables) >= 1

    def test_get_table_schema_includes_example_values_for_varchar(self, db_path: str) -> None:
        # arrange — "items" has a VARCHAR "label" column with values "alpha", "beta"
        schema = DuckDbSqlEngine(db_path).get_table_schema("items")
        # assert — schema should mention the example values
        assert "alpha" in schema or "beta" in schema

    def test_nullable_column_has_no_not_null_annotation(self, db_path: str) -> None:
        # arrange — "items" has nullable columns (no NOT NULL constraint)
        schema = DuckDbSqlEngine(db_path).get_table_schema("items")
        # assert — kills mutmut_7 (nullable="XXXX"), mutmut_8 (.lower()), mutmut_9 (str(None)),
        # mutmut_12 ("XXYESXX"), mutmut_13 ("yes" lowercase)
        assert "NOT NULL" not in schema

    def test_example_values_joined_with_comma_space(self, db_path: str) -> None:
        # arrange — "label" has "alpha" and "beta"
        schema = DuckDbSqlEngine(db_path).get_table_schema("items")
        # assert — separator is ", " not "XX, XX" (kills _sample_values mutmut_18)
        assert "XX, XX" not in schema
        # both values must be present (they share a correct separator)
        assert "alpha" in schema
        assert "beta" in schema

    def test_integer_column_has_no_example_suffix(self, db_path: str) -> None:
        # arrange — "id" is INTEGER, so no examples should be shown
        schema = DuckDbSqlEngine(db_path).get_table_schema("items")
        # assert — kills mutmut_26 (suffix="XXXX" when no examples) for non-textual columns
        assert "XXXX" not in schema

    def test_validate_table_name_accepts_mixed_case(self) -> None:
        # arrange — "MyTable" starts with uppercase; mutmut_7 uses [a-za-z_] (lowercase only)
        # act / assert — must not raise
        DuckDbSqlEngine._validate_table_name("MyTable")

    def test_all_null_column_produces_empty_example_string(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        # kills _sample_values__mutmut_12 (return "XXXX" instead of "")
        # arrange — column with all NULL values
        path = str(tmp_path / "nullcol.duckdb")  # type: ignore[operator]
        with duckdb.connect(path) as conn:
            conn.execute("CREATE TABLE t (label VARCHAR)")
            conn.execute("INSERT INTO t VALUES (NULL), (NULL)")
        schema = DuckDbSqlEngine(path).get_table_schema("t")
        # with no non-null values, _sample_values returns "" → no "Examples:" annotation
        assert "XXXX" not in schema
        assert "Examples: " not in schema

    def test_exactly_low_cardinality_max_values_are_shown(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        # kills _sample_values__mutmut_15 (>= instead of > _LOW_CARDINALITY_MAX)
        # arrange — column with exactly 20 distinct values (= _LOW_CARDINALITY_MAX)
        path = str(tmp_path / "card20.duckdb")  # type: ignore[operator]
        values = ", ".join(f"('{chr(ord('a') + i)}{i}')" for i in range(20))
        with duckdb.connect(path) as conn:
            conn.execute("CREATE TABLE t (label VARCHAR)")
            conn.execute(f"INSERT INTO t VALUES {values}")
        schema = DuckDbSqlEngine(path).get_table_schema("t")
        # exactly 20 distinct values → NOT high cardinality → example annotation must appear
        assert "-- e.g." in schema


class TestReadOnlyConnection:
    """The SQL reaching execute_query is model-authored, so writes must be refused.

    _connect()'s read_only=True is the containment boundary: without it a hallucinated
    or injected DROP/UPDATE would silently mutate the user's database. These tests pin
    that invariant — deleting read_only=True previously survived mutation testing
    because nothing in the suite asserted it.
    """

    def test_rejects_ddl_that_creates_a_table(self, db_path: str) -> None:
        # kills _connect__mutmut_1 (read_only=True dropped from duckdb.connect)
        with pytest.raises(duckdb.InvalidInputException, match="read-only mode"):
            DuckDbSqlEngine(db_path).execute_query("CREATE TABLE injected (i INTEGER)")

    def test_rejects_ddl_that_drops_a_table(self, db_path: str) -> None:
        with pytest.raises(duckdb.InvalidInputException, match="read-only mode"):
            DuckDbSqlEngine(db_path).execute_query("DROP TABLE items")

    def test_rejects_dml_that_inserts_rows(self, db_path: str) -> None:
        with pytest.raises(duckdb.InvalidInputException, match="read-only mode"):
            DuckDbSqlEngine(db_path).execute_query("INSERT INTO items VALUES (3, 'gamma')")

    def test_rejects_dml_that_updates_rows(self, db_path: str) -> None:
        with pytest.raises(duckdb.InvalidInputException, match="read-only mode"):
            DuckDbSqlEngine(db_path).execute_query("UPDATE items SET label = 'overwritten'")

    def test_a_refused_write_leaves_the_data_untouched(self, db_path: str) -> None:
        # arrange
        engine = DuckDbSqlEngine(db_path)

        # act — the write is refused …
        with pytest.raises(duckdb.InvalidInputException):
            engine.execute_query("DELETE FROM items")

        # assert — … and the rows it targeted are still there
        assert engine.execute_query("SELECT count(*) AS n FROM items").rows == [(2,)]

    def test_reads_are_unaffected(self, db_path: str) -> None:
        # the guard must refuse writes without costing us the read path
        engine = DuckDbSqlEngine(db_path)
        assert engine.list_tables() == ["items"]
        assert engine.execute_query("SELECT label FROM items ORDER BY id").rows == [
            ("alpha",),
            ("beta",),
        ]
