"""Use case: list the dataset's table names."""

from shared.application.ports.sql_engine_port import SqlEnginePort


class ListDatasetTables:
    """Names every table in the connected dataset.

    Backs the composer's ``@`` mention menu: the client offers these names so a question
    carries an identifier the engine actually has, instead of one the model has to guess
    at. Names only — describing every table up front is what ``SqlEnginePort`` warns
    against, so columns are fetched per table, on demand.

    Example:
        tables = ListDatasetTables(engine).execute()
        # tables == ["events", "customers"]
    """

    def __init__(self, sql_engine: SqlEnginePort) -> None:
        """Wire the SQL engine the names are read from."""
        self._engine = sql_engine

    def execute(self) -> list[str]:
        """Return the dataset's table names."""
        return self._engine.list_tables()
