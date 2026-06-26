"""LangGraph node that recommends how to visualize a query result."""

from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.view_spec import ViewSpec
from shared.domain.value_objects.query_result import QueryResult

_SYSTEM_PROMPT = (
    "You are a data-visualization assistant. Given a question and the columns of a "
    "SQL result (with a small sample of rows), recommend how to present the answer.\n\n"
    "- Add a KPI for each headline single-number metric, referencing the column that "
    "holds it.\n"
    "- Add a chart only when the shape fits: a category/time column for labels plus one "
    "or more numeric columns for series. Prefer 'line' for time series, 'bar' for "
    "categories, 'pie' for parts of a whole.\n"
    "- Set show_table to true when the row-level detail is worth showing.\n"
    "- Reference columns by their exact names. Never invent columns or values."
)

_SAMPLE_ROW_LIMIT = 5


def _build_human_content(question: str, query_result: QueryResult) -> str:
    """Build the prompt body from the question, columns, and a small row sample."""
    sample = query_result.rows[:_SAMPLE_ROW_LIMIT]
    return (
        f"Question: {question}\n\n"
        f"Columns: {query_result.columns}\n\n"
        f"Sample rows (first {len(sample)} of {query_result.row_count}): {sample}"
    )


class RecommendView:
    """Node that uses an LLM with structured output to recommend a ViewSpec.

    Runs only on the success path: when the SQL produced no result there is nothing
    to visualize, so it returns an empty update and assemble_view falls back to a
    narrative-only tree. The model sees only column names and a few sample rows —
    never the full dataset — so prompt size stays bounded.

    Example:
        node = RecommendView(chat_model)
        result = node({"question": "Revenue by month", "query_result": ...})
        # result == {"view_spec": ViewSpec(...)}
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        """Wire the chat model as a structured-output runnable."""
        self._model: Runnable[LanguageModelInput, ViewSpec] = cast(
            Runnable[LanguageModelInput, ViewSpec],
            chat_model.with_structured_output(ViewSpec),
        )

    def __call__(self, state: ChatState) -> dict[str, ViewSpec]:
        """Recommend a ViewSpec, or return {} when there is no result to visualize."""
        query_result = cast(dict[str, object], state).get("query_result")
        if not isinstance(query_result, QueryResult):
            return {}
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=_build_human_content(state["question"], query_result)),
        ]
        return {"view_spec": self._model.invoke(messages)}
