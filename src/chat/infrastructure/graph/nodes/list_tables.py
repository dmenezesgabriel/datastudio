"""LangGraph node that lists available tables from the SQL engine."""

from chat.infrastructure.graph.chat_state import ChatState
from shared.application.ports.sql_engine_port import SqlEnginePort


class ListTables:
    """Node that lists all available tables from the SQL engine.

    Example:
        node = ListTables(engine)
        result = node({"question": "How many rows?"})
        # result == {"tables": ["events", "customers"]}
    """

    def __init__(self, sql_engine: SqlEnginePort) -> None:
        """Inject the SQL engine."""
        self._engine = sql_engine

    def __call__(self, state: ChatState) -> dict[str, list[str]]:
        """List all available tables from the SQL engine."""
        return {"tables": self._engine.list_tables()}
