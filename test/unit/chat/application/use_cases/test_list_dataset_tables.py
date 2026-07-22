"""Tests for the ListDatasetTables use case (names the composer can offer as mentions)."""

from chat.application.use_cases.list_dataset_tables import ListDatasetTables
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine


class TestListDatasetTables:
    def test_returns_the_engines_table_names(self) -> None:
        # arrange
        engine = FakeSqlEngine(tables=["events", "customers"])
        # act
        tables = ListDatasetTables(engine).execute()
        # assert
        assert tables == ["events", "customers"]

    def test_empty_dataset_returns_no_tables(self) -> None:
        # arrange
        engine = FakeSqlEngine(tables=[])
        # act
        tables = ListDatasetTables(engine).execute()
        # assert
        assert tables == []

    def test_asks_the_engine_once_per_call(self) -> None:
        # The composer prewarms this on focus, so a redundant round trip per call would be
        # paid on every visit to the field.
        # arrange
        engine = FakeSqlEngine(tables=["events"])
        use_case = ListDatasetTables(engine)
        # act
        use_case.execute()
        # assert
        assert engine.list_tables_calls == 1
