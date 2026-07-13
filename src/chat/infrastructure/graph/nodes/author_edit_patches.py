"""LangGraph node: author a restyle edit as JSON-Patch lines against existing elements.

The cheap edit path (no SQL). The LLM sees the dashboard's current elements and the
user's instruction, and emits RFC-6902 patch lines that modify what is already there —
switching a chart ``kind``, renaming a ``title``, or reordering a region's children to
move widgets around. Reserved elements (root, narrative, a frame's SQL) are filtered out
so a restyle can only touch the widget visualizations, never the layout scaffolding.
"""

import json
from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from chat.domain.value_objects.render_tree import RenderTree
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes.generate_widget_view import keep_valid_patch_lines
from chat.infrastructure.graph.response_content_extractor import ResponseContentExtractor
from chat.infrastructure.graph.step_tags import step_tag

_RESTYLE_INSTRUCTIONS = (
    "You are editing an existing dashboard by emitting RFC-6902 JSON-Patch lines that modify "
    "its current elements (given below). Emit ONE patch per line and nothing else. Rules:\n"
    "- Only touch existing element ids under /elements/<id>. Do not add or remove widgets, and "
    "never touch /elements/root, /elements/narrative, or a frame's sql prop.\n"
    "- Switch a chart type with replace /elements/<id>/props/kind to 'bar', 'line', or 'pie'.\n"
    "- Rename with replace /elements/<id>/props/title (or /props/label for a KpiStat).\n"
    "- Reorder or move widgets by replacing a region's children array, e.g. replace "
    "/elements/grid/children with the reordered list of frame ids (a widget's frame is "
    "'<widget-id>-frame'); the regions are 'kpi-row' and 'grid'.\n"
    "- Keep every $state binding and column name exactly as-is.\n"
    "Emit only the patch lines the instruction requires."
)


class AuthorEditPatches:
    """Node that turns a restyle instruction into validated ``/elements`` patch lines.

    Example:
        node = AuthorEditPatches(model, catalog_prompt, extractor)
        node({"instruction": "make widget-0 a line chart", "prior_spec": spec})
        # → {"widget_patch_lines": ['{"op":"replace","path":".../props/kind","value":"line"}']}
    """

    def __init__(
        self,
        chat_model: BaseChatModel,
        catalog_prompt: str,
        content_extractor: ResponseContentExtractor,
    ) -> None:
        """Wire the model, the catalog vocabulary prompt, and the response text extractor."""
        self._model: Runnable[LanguageModelInput, BaseMessage] = chat_model.with_config(
            {"tags": [step_tag("author_edit_patches")]}
        )
        self._system_prompt = f"{catalog_prompt}\n\n{_RESTYLE_INSTRUCTIONS}"
        self._extractor = content_extractor

    def __call__(self, state: ChatState) -> dict[str, object]:
        """Author and validate the restyle patch lines for the instruction in state."""
        state_dict = cast(dict[str, object], state)
        instruction = cast(str, state_dict["instruction"])
        spec = cast(RenderTree, state_dict["prior_spec"])
        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=_human_content(instruction, spec)),
        ]
        text = self._extractor.extract(self._model.invoke(messages))
        return {"widget_patch_lines": keep_valid_patch_lines(text)}


def _human_content(instruction: str, spec: RenderTree) -> str:
    """Build the prompt: the instruction plus the dashboard's current elements as JSON."""
    elements = json.dumps(
        {eid: element.model_dump() for eid, element in spec.elements.items()}, ensure_ascii=False
    )
    return f"Instruction: {instruction}\n\nCurrent elements:\n{elements}"
