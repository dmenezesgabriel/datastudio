"""Immutable result of answering one question through the text2sql engine."""

from dataclasses import dataclass

from chat.domain.value_objects.render_tree import RenderTree


@dataclass(frozen=True)
class Text2SqlResult:
    """What the text2sql engine returns for a single question.

    Bundles the natural-language answer and the renderable presentation tree (which
    already carries each widget's SQL for disclosure), so the application layer never
    touches the graph.

    Example:
        Text2SqlResult(narrative="There are 42 events.", view=tree)
    """

    narrative: str
    view: RenderTree
