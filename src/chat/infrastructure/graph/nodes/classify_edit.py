"""LangGraph node: classify a dashboard edit and route it to the cheapest handler.

The router of the edit flow. Given the user's instruction and the current dashboard,
it picks a mode: ``restyle`` — a presentational change (chart kind, title, widget order)
authored as patches against the existing elements, no SQL — or ``reanalyze`` — a change
that needs new data (a different breakdown, filter, or an added widget), rebuilt through
the single-widget SQL worker. Reusing widget ids keeps ``$state`` paths stable so a
reanalyzed widget replaces its predecessor in place instead of duplicating it.
"""

import re
from typing import Literal, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.widget import WidgetSpec
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes._structured_output import invoke_structured

_FRAME_SUFFIX = "-frame"

_SYSTEM_PROMPT = (
    "You are the router for a dashboard editor. The user wants to change an existing "
    "dashboard. Choose the cheapest MODE that satisfies the request:\n"
    "- 'restyle' — a presentational change to widgets that already exist: switch a chart "
    "kind (bar/line/pie), rename a title, or reorder/move widgets. No new data is needed.\n"
    "- 'reanalyze' — the request needs a NEW query: a different breakdown, grouping, filter, "
    "time range, or an added widget. Give the target widget (an existing id to replace, or "
    "empty to add a new one), a short title, a self-contained single-query sub_question, and "
    "its role ('metric' for one headline number, 'analysis' for a multi-row chart/table).\n"
    "Prefer 'restyle' when the existing data already supports the request."
)


class _EditPlan(BaseModel):
    mode: Literal["restyle", "reanalyze"] = "restyle"
    target_widget_id: str = ""
    title: str = ""
    sub_question: str = ""
    role: Literal["metric", "analysis"] = "analysis"


class ClassifyEdit:
    """Node that classifies an edit as ``restyle`` or ``reanalyze`` and seeds its state.

    Example:
        node = ClassifyEdit(chat_model)
        node({"instruction": "make it a line chart", "prior_spec": spec})
        # → {"edit_mode": "restyle"}
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        """Wire the chat model as a structured-output runnable."""
        self._model: Runnable[LanguageModelInput, _EditPlan] = cast(
            Runnable[LanguageModelInput, _EditPlan],
            chat_model.with_structured_output(_EditPlan),
        )

    def __call__(self, state: ChatState) -> dict[str, object]:
        """Classify the edit; for a reanalyze, seed the target widget and its sub-question."""
        state_dict = cast(dict[str, object], state)
        instruction = cast(str, state_dict["instruction"])
        spec = cast(RenderTree, state_dict["prior_spec"])
        plan = invoke_structured(self._model, self._messages(instruction, spec), "classify_edit")
        if plan is None or plan.mode == "restyle":
            return {"edit_mode": "restyle"}
        return self._reanalyze(plan, instruction, spec)

    def _messages(self, instruction: str, spec: RenderTree) -> list[BaseMessage]:
        """Build ``[System, Human]`` with the instruction and the current widgets."""
        human_content = f"Instruction: {instruction}\n\nCurrent widgets:\n{_describe_widgets(spec)}"
        return [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=human_content)]

    def _reanalyze(self, plan: _EditPlan, instruction: str, spec: RenderTree) -> dict[str, object]:
        """Resolve the widget id to (re)build and seed the SQL worker's inputs."""
        existing = _widget_ids(spec)
        widget_id = plan.target_widget_id if plan.target_widget_id in existing else _next_id(spec)
        sub_question = plan.sub_question.strip() or instruction
        widget = WidgetSpec(
            id=widget_id,
            title=plan.title.strip() or "Analysis",
            sub_question=sub_question,
            role=plan.role,
        )
        return {
            "edit_mode": "reanalyze",
            "target_widget_id": widget_id,
            "question": sub_question,
            "widget": widget,
        }


def _widget_ids(spec: RenderTree) -> list[str]:
    """The ids of the widgets currently on the dashboard, in layout order."""
    return [k[: -len(_FRAME_SUFFIX)] for k in spec.elements if k.endswith(_FRAME_SUFFIX)]


def _next_id(spec: RenderTree) -> str:
    """Mint a fresh, collision-free ``widget-N`` id for an added widget."""
    matches = (re.fullmatch(r"widget-(\d+)", wid) for wid in _widget_ids(spec))
    numbers = [int(m.group(1)) for m in matches if m is not None]
    return f"widget-{max(numbers) + 1 if numbers else 0}"


def _describe_widgets(spec: RenderTree) -> str:
    """List each widget as ``- <id> (<leaf type>): <title>`` for the router prompt."""
    lines = [f"- {wid} ({_kind(spec, wid)}){_title(spec, wid)}" for wid in _widget_ids(spec)]
    return "\n".join(lines) or "(no widgets yet)"


def _leaf(spec: RenderTree, widget_id: str) -> RenderElement | None:
    """The widget's visualization element (the frame's single child), if present."""
    frame = spec.elements.get(f"{widget_id}{_FRAME_SUFFIX}")
    if frame is None or not frame.children:
        return None
    return spec.elements.get(frame.children[0])


def _kind(spec: RenderTree, widget_id: str) -> str:
    """The widget's component type (e.g. ``ChartJs``), or ``?`` when unknown."""
    leaf = _leaf(spec, widget_id)
    return leaf.type if leaf is not None else "?"


def _title(spec: RenderTree, widget_id: str) -> str:
    """A trailing ``": <title>"`` from the widget's title/label prop, or empty."""
    leaf = _leaf(spec, widget_id)
    if leaf is None:
        return ""
    for key in ("title", "label"):
        value = leaf.props.get(key)
        if isinstance(value, str) and value:
            return f": {value}"
    return ""
