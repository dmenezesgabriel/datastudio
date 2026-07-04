"""LangGraph orchestrator node: classify a turn and plan its dashboard widgets.

The planner of the orchestrator–workers pattern. It first classifies the turn:
a ``"text"`` question (greeting, definition, capability/meta) is answered directly
with no SQL; a ``"data"`` question is decomposed into 1..N widgets — one focused
question yields a single widget, a broad/open-ended one an F-layout dashboard —
each a sub-question answerable by a single SQL query. The graph then either routes
to ``answer_text`` or fans out one parallel ``build_widget`` worker per spec. Widget
ids are assigned here (not taken from the model) so ``$state`` paths and element ids
never collide.
"""

from typing import Literal, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.widget import WidgetSpec
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes._structured_output import invoke_structured

_MAX_WIDGETS = 5

_SYSTEM_PROMPT = (
    "You are the planner for a business-intelligence assistant. Given a question and the "
    "database schema, first choose a KIND, then plan the answer.\n"
    "KIND:\n"
    "- 'text' — the question needs no data query: a greeting, a definition, a capability or "
    "meta question ('what can you do?', 'which tables are there?'), a clarification, or small "
    "talk. Write a brief, direct reply in `text_answer` and return no widgets. Choose this "
    "ONLY when running SQL would add nothing.\n"
    "- 'data' — the question is about the data. Plan 1..N dashboard widgets, each ONE "
    "sub-question answerable by a single SQL query and shown as one chart, KPI, or table.\n"
    "For 'data', choose BREADTH by the question's intent, not by keywords:\n"
    "- ONE widget for a single focused ask — a metric, ranking, 'top N', lookup, or one "
    "breakdown. Use a single sub_question that mirrors the user's question directly.\n"
    "- A DASHBOARD of 3-5 widgets when the question is broad, open-ended, exploratory, or a "
    "health check ('how are sales doing?', 'give me the picture', 'tell me about <subject>', "
    "or a bare table/subject name). Business users want an overview even when they don't say "
    "'dashboard' — serve it. Compose most-important-first: lead with the headline single-value "
    "KPI, then the primary trend or breakdown, then supporting breakdowns or a detail list — "
    "each a distinct, non-overlapping sub_question.\n"
    "- When unsure, prefer a small dashboard (2-3 widgets) for a vague question and a single "
    "widget for a precise one.\n"
    "- Give each widget a short title and a precise, self-contained sub_question. Never "
    "propose data the schema does not support.\n"
    "- Earlier conversation turns, when present, are context for follow-ups (e.g. 'break "
    "it down by month'): resolve references against them, but plan for the CURRENT question."
)


class _WidgetIntent(BaseModel):
    title: str
    sub_question: str


class _WidgetPlan(BaseModel):
    # Defaults let the model omit fields per kind: a "text" plan needs no widgets,
    # a "data" plan no text_answer. Pydantic copies the mutable default per instance.
    kind: Literal["data", "text"] = "data"
    text_answer: str = ""
    widgets: list[_WidgetIntent] = []  # noqa: RUF012


class PlanWidgets:
    """Node that uses an LLM to classify a turn and plan its dashboard widgets.

    Example:
        node = PlanWidgets(chat_model)
        result = node({"question": "Overview", "schema": "...", "history": []})
        # result == {"answer_kind": "data", "widget_specs": [WidgetSpec("widget-0", ...), ...]}
    """

    def __init__(self, chat_model: BaseChatModel, max_widgets: int = _MAX_WIDGETS) -> None:
        """Wire the chat model as a structured-output runnable and the widget cap."""
        self._model: Runnable[LanguageModelInput, _WidgetPlan] = cast(
            Runnable[LanguageModelInput, _WidgetPlan],
            chat_model.with_structured_output(_WidgetPlan),
        )
        self._max_widgets = max_widgets

    def __call__(self, state: ChatState) -> dict[str, object]:
        """Classify the turn: a text answer, or a plan of collision-free widget ids."""
        plan = invoke_structured(self._model, self._messages(state), "plan_widgets")
        if plan is not None and _is_text_answer(plan):
            return {"answer_kind": "text", "text_answer": plan.text_answer.strip()}
        return {"answer_kind": "data", "widget_specs": self._specs(plan, state["question"])}

    def _messages(self, state: ChatState) -> list[BaseMessage]:
        """Build ``[System, *history, Human]`` — prior turns as short-term memory."""
        human_content = f"Question: {state['question']}\n\nSchema:\n{state['schema']}"
        return [
            SystemMessage(content=_SYSTEM_PROMPT),
            *state["history"],
            HumanMessage(content=human_content),
        ]

    def _specs(self, plan: _WidgetPlan | None, question: str) -> list[WidgetSpec]:
        """Assign sequential ids to the planned widgets; fall back to one on an empty plan."""
        intents = list(plan.widgets)[: self._max_widgets] if plan is not None else []
        if not intents:
            return [_fallback_widget(question)]
        return [
            WidgetSpec(id=f"widget-{index}", title=intent.title, sub_question=intent.sub_question)
            for index, intent in enumerate(intents)
        ]


def _is_text_answer(plan: _WidgetPlan) -> bool:
    """True when the planner chose a direct text reply with non-empty content.

    ``getattr`` (not ``plan.kind``) tolerates test doubles that predate the ``kind``
    field: a plan without it defaults to the ``data`` path, never a blank text answer.
    """
    is_text = getattr(plan, "kind", "data") == "text"
    return is_text and bool(getattr(plan, "text_answer", "").strip())


def _fallback_widget(question: str) -> WidgetSpec:
    """A single widget answering the original question, when the model plans nothing."""
    return WidgetSpec(id="widget-0", title="Answer", sub_question=question)
