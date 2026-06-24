from chat.application.ports.sql_engine_port import SqlEnginePort
from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.query_result import QueryResult


class ExecuteSql:
    """Node that runs the generated SQL query against the SQL engine.

    Example:
        node = ExecuteSql(engine)
        result = node({"sql_query": "SELECT COUNT(*) FROM orders"})
        # result == {"query_result": QueryResult(...)}
    """

    def __init__(self, sql_engine: SqlEnginePort) -> None:
        self._engine = sql_engine

    def __call__(self, state: ChatState) -> dict[str, QueryResult]:
        return {"query_result": self._engine.execute_query(state["sql_query"])}
