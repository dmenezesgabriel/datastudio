"""LangGraph orchestrator node: decompose a question into dashboard widgets.

This is the planner of the orchestrator–workers pattern: it decides 1..N widgets
(a narrow question yields one), each a focused sub-question answerable by a single
SQL query. The graph then fans out one parallel ``build_widget`` worker per spec.
Widget ids are assigned here (not taken from the model) so ``$state`` paths and
element ids never collide.
"""

from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.widget import WidgetSpec
from chat.infrastructure.graph.nodes._structured_output import invoke_structured

_MAX_WIDGETS = 5

_SYSTEM_PROMPT = (
    "You are a dashboard planner. Given a question and the database schema, decide which "
    "dashboard widgets to build. Each widget is ONE sub-question answerable by a single SQL "
    "query and shown as one chart, KPI, or table.\n"
    "- DEFAULT TO EXACTLY ONE widget. Almost every question — any single metric, ranking, "
    "'top N', breakdown, or list — is one widget. Use a single sub_question that mirrors the "
    "user's question as directly as possible.\n"
    "- Return MULTIPLE widgets (2-5) ONLY when the question explicitly asks for an 'overview', "
    "'dashboard', 'summary', or several distinct metrics at once. When unsure, return one.\n"
    "- When you DO return multiple widgets, compose a coherent dashboard ordered "
    "most-important first: lead with the headline metric (a single-value KPI), then the "
    "primary trend or breakdown, then supporting breakdowns or a detail list — each a "
    "distinct, non-overlapping sub_question.\n"
    "- Give each widget a short title and a precise, self-contained sub_question.\n"
    "- Never propose data the schema does not support.\n"
    "- Earlier conversation turns, when present, are context for follow-ups (e.g. 'break "
    "it down by month'): resolve references against them, but plan for the CURRENT question."
)


class _WidgetIntent(BaseModel):
    title: str
    sub_question: str


class _WidgetPlan(BaseModel):
    widgets: list[_WidgetIntent]


class PlanWidgets:
    """Node that uses an LLM with structured output to plan dashboard widgets.

    Example:
        node = PlanWidgets(chat_model)
        result = node({"question": "Sales overview", "schema": "..."})
        # result == {"widget_specs": [WidgetSpec(id="widget-0", ...), ...]}
    """

    def __init__(self, chat_model: BaseChatModel, max_widgets: int = _MAX_WIDGETS) -> None:
        """Wire the chat model as a structured-output runnable and the widget cap."""
        self._model: Runnable[LanguageModelInput, _WidgetPlan] = cast(
            Runnable[LanguageModelInput, _WidgetPlan],
            chat_model.with_structured_output(_WidgetPlan),
        )
        self._max_widgets = max_widgets

    def __call__(self, state: ChatState) -> dict[str, list[WidgetSpec]]:
        """Plan the widgets, assigning collision-free ids; fall back to one on an empty plan."""
        human_content = f"Question: {state['question']}\n\nSchema:\n{state['schema']}"
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            *state["history"],
            HumanMessage(content=human_content),
        ]
        plan = invoke_structured(self._model, messages, "plan_widgets")
        intents = list(plan.widgets)[: self._max_widgets] if plan is not None else []
        if not intents:
            return {"widget_specs": [_fallback_widget(state["question"])]}
        specs = [
            WidgetSpec(id=f"widget-{index}", title=intent.title, sub_question=intent.sub_question)
            for index, intent in enumerate(intents)
        ]
        return {"widget_specs": specs}


def _fallback_widget(question: str) -> WidgetSpec:
    """A single widget answering the original question, when the model plans nothing."""
    return WidgetSpec(id="widget-0", title="Answer", sub_question=question)
