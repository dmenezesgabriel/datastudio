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
    "You are a helpful data analyst. Given a question and the SQL query results, "
    "provide a concise natural language answer. Do not include the SQL or the raw table.\n\n"
    "Number formatting:\n"
    "- Format large integers and decimals with thousands separators "
    "(e.g. 1,234,567 or 13,591,643.70). Use exactly two decimal places for monetary values.\n"
    '- Do not rescale values (do not write "13.6M" when the exact figure is available).\n'
    "- If the result already contains a percentage value (e.g. 91.88), report it as 91.88%. "
    "Do not compute percentages yourself.\n\n"
    "Attribution: Ground your answer by stating the number of records the result is based on "
    "when it adds meaningful context "
    '(e.g. "Based on 112,650 delivered orders, 91.88% arrived on time."). '
    "Omit attribution when the scope is obvious from the question itself."
)

_NO_RESULT_RESPONSE = (
    "I couldn't answer that question — the generated query failed to run against the "
    "database. Please try rephrasing the question."
)


def _build_human_content(question: str, query_result: QueryResult) -> str:
    """Builds the human turn content for the format prompt.

    Example:
        content = _build_human_content("Total revenue?", result)
    """
    count = query_result.row_count
    label = f"{count} row{'s' if count != 1 else ''}"
    return f"Question: {question}\n\nResults ({label}):\n{query_result.to_markdown_table()}"


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
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=_build_human_content(state["question"], query_result)),
        ]
        result: _AnswerOutput = self._model.invoke(messages)
        return {"response": result.answer}
