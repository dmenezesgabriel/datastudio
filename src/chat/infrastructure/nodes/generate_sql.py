from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState

_SYSTEM_PROMPT = (
    "You are a SQL expert. Given a database schema and a natural language question, "
    "write a single DuckDB-compatible SELECT query that answers the question."
)


class _SqlOutput(BaseModel):
    sql: str


class GenerateSql:
    """Node that uses an LLM with structured output to generate a SQL query.

    Example:
        node = GenerateSql(chat_model)
        result = node({"schema": "-- orders\\nid INT", "question": "Count orders"})
        # result == {"sql_query": "SELECT COUNT(*) FROM orders"}
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        self._model = chat_model.with_structured_output(_SqlOutput)

    def __call__(self, state: ChatState) -> dict[str, str]:
        human_content = f"Schema:\n{state['schema']}\n\nQuestion: {state['question']}"
        messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=human_content)]
        result: _SqlOutput = self._model.invoke(messages)  # type: ignore[assignment]
        return {"sql_query": result.sql}
