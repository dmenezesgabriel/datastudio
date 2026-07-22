"""Tests for the DescribeDatasetTable use case (one table's columns, for @-references)."""

import pytest

from chat.application.use_cases.describe_dataset_table import DescribeDatasetTable
from chat.domain.errors import TableNotFoundError
from shared.domain.value_objects.table_schema import ColumnDescriptor
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine


def _engine() -> FakeSqlEngine:
    return FakeSqlEngine(
        tables=["events", "customers"],
        columns={
            "events": (
                ColumnDescriptor(name="amount", data_type="DOUBLE"),
                ColumnDescriptor(name="category", data_type="VARCHAR"),
            )
        },
    )


class TestDescribeDatasetTable:
    def test_returns_the_tables_columns(self) -> None:
        # arrange
        use_case = DescribeDatasetTable(_engine())
        # act
        schema = use_case.execute("events")
        # assert
        assert schema.name == "events"
        assert [c.name for c in schema.columns] == ["amount", "category"]

    def test_unknown_table_is_not_found(self) -> None:
        # arrange
        use_case = DescribeDatasetTable(_engine())
        # act / assert — the offending name is in the message
        with pytest.raises(TableNotFoundError, match="absent_table"):
            use_case.execute("absent_table")

    def test_never_describes_a_table_the_dataset_does_not_list(self) -> None:
        # The name is interpolated into DESCRIBE by the engine, so membership of the
        # dataset's own table list is the whitelist that decides what may be described.
        engine = _engine()
        use_case = DescribeDatasetTable(engine)
        # act
        with pytest.raises(TableNotFoundError):
            use_case.execute("events; DROP TABLE events")
        # assert
        assert engine.described_tables == []
