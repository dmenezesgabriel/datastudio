"""LangGraph node that generates SQL from a natural language question."""

from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.step_tags import step_tag

_SYSTEM_PROMPT = (
    "You are a SQL expert. Given a DuckDB database schema and a natural language "
    "question, write a single DuckDB-compatible SELECT query that answers it.\n"
    "- Return exactly one SELECT statement; compute everything inside SQL. For "
    "comparisons across periods or groups, use CASE WHEN, conditional aggregation, "
    "or subqueries within the single statement.\n"
    "- First pin down the exact metric and grain the question asks for: WHAT is measured "
    "(the aggregate), PER what group/unit, over WHAT scope. Make the SELECT return precisely "
    "that — the right measure at the right grain. A query that returns the right number of "
    "rows but the wrong measure, aggregate, or grouping is wrong.\n"
    "- Apply EVERY qualifier the question states as a filter: a named status, subset, "
    "category, or time range restricts the rows (e.g. a question about one status or one "
    "period must add the matching WHERE clause). Never silently broaden the scope the "
    "question asked for.\n"
    "- For literal filters, reuse the sample values shown in the schema comments "
    "(`-- e.g. ...`), matching their exact spelling and case.\n"
    "- When the question asks which SINGLE item ranks highest — the most, the largest, the "
    "top, the dominant one — and expects ONE answer, return only that row: ORDER BY the "
    "measure DESC LIMIT 1. Return several rows ONLY when the question asks for them "
    "explicitly ('top N', 'each', 'per', 'list', 'breakdown', 'by <category>').\n"
    "- Use DuckDB date/time functions (date_diff, date_part, strftime) for date logic.\n"
    "- Express a share, proportion, rate, or percentage on a 0–100 percentage scale "
    "(multiply the ratio by 100), not as a 0–1 fraction.\n"
    "- When aggregating or computing a rate over a column that may be NULL, treat NULL as "
    "unknown, not as a value: exclude NULL rows from both the numerator and the denominator "
    "(e.g. WHERE <col> IS NOT NULL). Never count NULL as zero or as failing a condition.\n"
    "- Reference columns exactly as named in the schema.\n"
    "- Use ONLY columns the schema defines. Never invent a column, and never compute a metric "
    "the schema cannot support (e.g. a profit or margin with no cost column) by substituting an "
    "unrelated column as a proxy — a query that runs but answers a different question is wrong."
)


class _SqlOutput(BaseModel):
    sql: str


class GenerateSql:
    r"""Node that uses an LLM with structured output to generate a SQL query.

    Example:
        node = GenerateSql(chat_model)
        result = node({"schema": "-- events\nid INT", "question": "Count events"})
        # result == {"sql": "SELECT COUNT(*) FROM events"}
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        """Wire the chat model as a structured-output runnable."""
        self._model: Runnable[LanguageModelInput, _SqlOutput] = cast(
            Runnable[LanguageModelInput, _SqlOutput],
            chat_model.with_structured_output(_SqlOutput).with_config(
                {"tags": [step_tag("generate_sql")]}
            ),
        )

    def __call__(self, state: ChatState) -> dict[str, str]:
        """Generate a SQL query from the schema and question in state."""
        human_content = f"Schema:\n{state['schema']}\n\nQuestion: {state['question']}"
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]
        result: _SqlOutput = self._model.invoke(messages)
        return {"sql": result.sql}
