from chat.domain.value_objects.chat_state import ChatState
from shared.application.ports.sql_engine_port import SqlEnginePort


class GetSchema:
    """Node that fetches the schema for every table listed in state.

    Example:
        node = GetSchema(engine)
        result = node({"tables": ["orders"], ...})
        # result == {"schema": "-- orders\\nid INTEGER\\n..."}
    """

    def __init__(self, sql_engine: SqlEnginePort) -> None:
        self._engine = sql_engine

    def __call__(self, state: ChatState) -> dict[str, str]:
        schemas = [self._engine.get_table_schema(t) for t in state["tables"]]
        return {"schema": "\n\n".join(schemas)}
