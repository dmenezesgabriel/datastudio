"""LangGraph node that generates SQL from a natural language question."""

from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState

_SYSTEM_PROMPT = (
    "You are a SQL expert. Given a DuckDB database schema and a natural language "
    "question, write a single DuckDB-compatible SELECT query that answers it.\n"
    "- Return exactly one SELECT statement; compute everything inside SQL. For "
    "comparisons across periods or groups, use CASE WHEN, conditional aggregation, "
    "or subqueries within the single statement.\n"
    "- For literal filters, reuse the sample values shown in the schema comments "
    "(`-- e.g. ...`), matching their exact spelling and case.\n"
    "- Use DuckDB date/time functions (date_diff, date_part, strftime) for date logic.\n"
    "- When aggregating or computing a rate over a column that may be NULL, treat NULL as "
    "unknown, not as a value: exclude NULL rows from both the numerator and the denominator "
    "(e.g. WHERE <col> IS NOT NULL). Never count NULL as zero or as failing a condition.\n"
    "- Reference columns exactly as named in the schema."
)


class _SqlOutput(BaseModel):
    sql: str


class GenerateSql:
    r"""Node that uses an LLM with structured output to generate a SQL query.

    Example:
        node = GenerateSql(chat_model)
        result = node({"schema": "-- orders\nid INT", "question": "Count orders"})
        # result == {"sql_query": "SELECT COUNT(*) FROM orders"}
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        """Wire the chat model as a structured-output runnable."""
        self._model: Runnable[LanguageModelInput, _SqlOutput] = cast(
            Runnable[LanguageModelInput, _SqlOutput],
            chat_model.with_structured_output(_SqlOutput),
        )

    def __call__(self, state: ChatState) -> dict[str, str]:
        """Generate a SQL query from the schema and question in state."""
        human_content = f"Schema:\n{state['schema']}\n\nQuestion: {state['question']}"
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]
        result: _SqlOutput = self._model.invoke(messages)
        return {"sql_query": result.sql}
