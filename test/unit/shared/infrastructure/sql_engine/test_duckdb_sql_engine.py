from pathlib import Path

import duckdb
import pytest

from shared.infrastructure.sql_engine.duckdb.duckdb_sql_engine import DuckDbSqlEngine


@pytest.fixture
def engine(tmp_path: Path) -> DuckDbSqlEngine:
    """A DuckDbSqlEngine over a temp database with one seeded table."""
    db_path = str(tmp_path / "test.duckdb")
    with duckdb.connect(db_path) as conn:
        conn.execute("CREATE TABLE cars (  name VARCHAR NOT NULL,  origin VARCHAR,  mpg DOUBLE)")
        conn.execute(
            "INSERT INTO cars VALUES "
            "('a','USA',18.0),('b','USA',20.0),('c','Japan',30.0),('d','Europe',25.0)"
        )
    return DuckDbSqlEngine(db_path)


class TestDuckDbSqlEngineSchemaEnrichment:
    def test_includes_sample_values_for_low_cardinality_text_column(
        self, engine: DuckDbSqlEngine
    ) -> None:
        # act
        schema = engine.get_table_schema("cars")
        # assert — the enumerable origin column gets example values for filtering
        assert "origin" in schema
        assert "e.g." in schema
        assert "USA" in schema

    def test_marks_not_null_columns(self, engine: DuckDbSqlEngine) -> None:
        # act
        schema = engine.get_table_schema("cars")
        # assert
        assert "name VARCHAR NOT NULL" in schema

    def test_omits_examples_for_numeric_columns(self, engine: DuckDbSqlEngine) -> None:
        # act
        line = next(
            ln for ln in engine.get_table_schema("cars").splitlines() if ln.startswith("mpg")
        )
        # assert — numeric columns carry no example values
        assert "e.g." not in line

    def test_starts_with_table_header(self, engine: DuckDbSqlEngine) -> None:
        # act
        schema = engine.get_table_schema("cars")
        # assert
        assert schema.startswith("-- cars\n")


class TestDuckDbSqlEngineScalability:
    def test_omits_examples_for_high_cardinality_text_column(self, tmp_path: Path) -> None:
        # arrange — 50 distinct ids: too many to enumerate; sampling must skip it
        db_path = str(tmp_path / "high.duckdb")
        with duckdb.connect(db_path) as conn:
            conn.execute("CREATE TABLE t (uid VARCHAR)")
            conn.executemany("INSERT INTO t VALUES (?)", [(f"id-{i}",) for i in range(50)])
        engine = DuckDbSqlEngine(db_path)
        # act
        schema = engine.get_table_schema("t")
        # assert — no example values are emitted for the high-cardinality column
        assert "e.g." not in schema
