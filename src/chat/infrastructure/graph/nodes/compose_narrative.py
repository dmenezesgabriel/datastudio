"""LangGraph node that writes the overall dashboard summary across all widgets.

Runs after fan-in, once every parallel ``build_widget`` worker has appended its
``WidgetResult``. It produces a short, deterministic narrative stating the key
figures exactly — the prose may cite numbers (that is its job); the chart/table
*data* still reaches the UI only via ``$state``, never through this model.
"""

from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.widget import WidgetResult
from chat.infrastructure.graph.nodes._structured_output import invoke_structured

_SYSTEM_PROMPT = (
    "You are a data analyst writing a brief dashboard summary. Given a question and the results "
    "behind each dashboard widget, write 1-3 sentences highlighting the key figures. Do not "
    "include SQL or raw tables.\n\n"
    "Number formatting:\n"
    "- Format large integers and decimals with thousands separators (e.g. 1,234,567 or "
    "13,591,643.70); use exactly two decimals for monetary values.\n"
    '- Do not rescale values (do not write "13.6M" when the exact figure is available).\n'
    "- Report every numeric value exactly as it appears; never multiply or divide it. Never "
    "convert between fractions and percentages: in a percentage column, 0.63 means 0.63% (not "
    "63%). Do not compute percentages yourself.\n"
    "- Cite figures from the widget results only; never invent numbers.\n"
    "- Earlier conversation turns, when present, are prior context; summarize the results "
    "for the CURRENT question and you may reference earlier answers naturally."
)

_NO_RESULT_RESPONSE = (
    "I couldn't build a dashboard for that question — the queries failed to run. "
    "Please try rephrasing the question."
)


def _fallback_summary(widget_results: list[WidgetResult]) -> str:
    """A deterministic summary naming the built widgets, when the model can't write prose.

    The figures still reach the UI via ``$state``; this only replaces the sentence.
    """
    titles = ", ".join(widget.title for widget in widget_results)
    return f"Here is your dashboard covering: {titles}."


class _AnswerOutput(BaseModel):
    answer: str


def _build_human_content(question: str, widget_results: list[WidgetResult]) -> str:
    """Build the summary prompt from the question and each widget's result table."""
    blocks = [
        f"Widget — {widget.title} ({widget.result.row_count} rows):\n"
        f"{widget.result.to_markdown_table()}"
        for widget in widget_results
    ]
    return f"Question: {question}\n\n" + "\n\n".join(blocks)


class ComposeNarrative:
    """Node that uses an LLM with structured output to summarize the dashboard.

    Example:
        node = ComposeNarrative(chat_model)
        node({"question": "overview", "widget_results": [WidgetResult(...), ...]})
        # → {"response": "Revenue grew 12% over the year across 5 categories."}
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        """Wire the chat model as a structured-output runnable."""
        self._model: Runnable[LanguageModelInput, _AnswerOutput] = cast(
            Runnable[LanguageModelInput, _AnswerOutput],
            chat_model.with_structured_output(_AnswerOutput),
        )

    def __call__(self, state: ChatState) -> dict[str, str]:
        """Summarize the widget results, or return a failure message when none ran."""
        raw = cast(dict[str, object], state).get("widget_results", [])
        results = [r for r in cast(list[object], raw) if isinstance(r, WidgetResult)]
        if not results:
            return {"response": _NO_RESULT_RESPONSE}
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            *state["history"],
            HumanMessage(content=_build_human_content(state["question"], results)),
        ]
        answer = invoke_structured(self._model, messages, "compose_narrative")
        if answer is None:
            return {"response": _fallback_summary(results)}
        return {"response": answer.answer}
