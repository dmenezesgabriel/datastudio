"""LangGraph node that formats SQL query results as natural language."""

from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState
from shared.domain.value_objects.query_result import QueryResult

_SYSTEM_PROMPT = (
    "You are a helpful data analyst. Given a question and the SQL query results as a table, "
    "provide a concise natural language answer. Do not include the SQL or the raw table.\n"
    "Report every numeric value exactly as it appears in the results: do not rescale, "
    "convert units, round beyond the given precision, or turn a value into a percentage "
    "yourself. If a column already holds a percentage (e.g. 0.63), state it as 0.63%."
)

_NO_RESULT_RESPONSE = (
    "I couldn't answer that question — the generated query failed to run against the "
    "database. Please try rephrasing the question."
)


class _AnswerOutput(BaseModel):
    answer: str


class FormatResponse:
    """Node that uses an LLM with structured output to format query results as natural language.

    Example:
        node = FormatResponse(chat_model)
        result = node({"question": "Count orders", "query_result": ..., "sql_query": ...})
        # result == {"response": "There are 42 orders."}
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        """Wire the chat model as a structured-output runnable."""
        self._model: Runnable[LanguageModelInput, _AnswerOutput] = cast(
            Runnable[LanguageModelInput, _AnswerOutput],
            chat_model.with_structured_output(_AnswerOutput),
        )

    def __call__(self, state: ChatState) -> dict[str, str]:
        """Format the query result as a natural language answer."""
        query_result = cast(dict[str, object], state).get("query_result")
        if not isinstance(query_result, QueryResult):
            return {"response": _NO_RESULT_RESPONSE}
        table = query_result.to_markdown_table()
        human_content = f"Question: {state['question']}\n\nResults:\n{table}"
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]
        result: _AnswerOutput = self._model.invoke(messages)
        return {"response": result.answer}
