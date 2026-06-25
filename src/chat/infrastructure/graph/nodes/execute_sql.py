"""LangGraph node that executes generated SQL against the database."""

from chat.domain.value_objects.chat_state import ChatState
from shared.application.ports.sql_engine_port import SqlEnginePort


class ExecuteSql:
    """Node that runs the generated SQL query against the SQL engine.

    On success it sets ``query_result`` and clears ``sql_error``. On failure it
    captures the error message in ``sql_error`` (without raising), so the graph
    can route to the repair loop instead of aborting the whole run.

    Example:
        node = ExecuteSql(engine)
        result = node({"sql_query": "SELECT COUNT(*) FROM orders"})
        # success → {"query_result": QueryResult(...), "sql_error": ""}
        # failure → {"sql_error": "Binder Error: ..."}
    """

    def __init__(self, sql_engine: SqlEnginePort) -> None:
        """Inject the SQL engine for query execution."""
        self._engine = sql_engine

    def __call__(self, state: ChatState) -> dict[str, object]:
        """Execute the SQL from state, returning query_result on success or sql_error on failure."""
        try:
            result = self._engine.execute_query(state["sql_query"])
            return {"query_result": result, "sql_error": ""}
        except Exception as exc:  # noqa: BLE001 — any engine error feeds the repair loop
            return {"sql_error": f"{type(exc).__name__}: {exc}"}
