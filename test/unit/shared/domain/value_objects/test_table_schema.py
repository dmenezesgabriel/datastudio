"""Tests for the TableSchema value object (a table's columns, as the engine reports them)."""

import pytest

from shared.domain.errors import InvariantViolationError
from shared.domain.value_objects.table_schema import ColumnDescriptor, TableSchema


class TestColumnDescriptor:
    def test_carries_a_column_name_and_its_type(self) -> None:
        # arrange / act
        column = ColumnDescriptor(name="amount", data_type="DOUBLE")
        # assert
        assert (column.name, column.data_type) == ("amount", "DOUBLE")

    def test_rejects_an_unnamed_column(self) -> None:
        # A nameless column cannot be referred to, so it must not reach the client.
        with pytest.raises(InvariantViolationError, match="name"):
            ColumnDescriptor(name="", data_type="DOUBLE")


class TestTableSchema:
    def test_carries_the_table_name_and_its_columns(self) -> None:
        # arrange
        columns = (ColumnDescriptor(name="amount", data_type="DOUBLE"),)
        # act
        schema = TableSchema(name="events", columns=columns)
        # assert
        assert schema.name == "events"
        assert schema.columns == columns

    def test_rejects_an_unnamed_table(self) -> None:
        with pytest.raises(InvariantViolationError, match="name"):
            TableSchema(name="", columns=())

    def test_a_table_with_no_columns_is_allowed(self) -> None:
        # An empty table is a real thing to describe; it simply offers nothing to reference.
        assert TableSchema(name="events", columns=()).columns == ()
