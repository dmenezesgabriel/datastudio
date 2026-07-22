"""Use case: describe one table of the dataset."""

from chat.domain.errors import TableNotFoundError
from shared.application.ports.sql_engine_port import SqlEnginePort
from shared.domain.value_objects.table_schema import TableSchema


class DescribeDatasetTable:
    """Names the columns of one table, so a question can refer to one of them.

    One table per call rather than a catalog-wide description — the reason
    ``SqlEnginePort`` gives: describing everything up front does not survive a
    warehouse-sized dataset.

    The table is checked against the dataset's own list before it is described. That is
    the domain question ("is this one of our tables?"), and it doubles as a whitelist:
    engines interpolate the name into DESCRIBE, because SQL has no bound form for an
    identifier.

    Example:
        schema = DescribeDatasetTable(engine).execute("events")
        # schema.columns[0].name == "amount"
    """

    def __init__(self, sql_engine: SqlEnginePort) -> None:
        """Wire the SQL engine the description is read from."""
        self._engine = sql_engine

    def execute(self, table_name: str) -> TableSchema:
        """Return the table's columns, or raise if the dataset has no such table."""
        if table_name not in self._engine.list_tables():
            raise TableNotFoundError(f"table {table_name!r} is not in the dataset")
        return self._engine.describe_table(table_name)
