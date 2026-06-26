"""Immutable result of answering one question through the text2sql engine."""

from dataclasses import dataclass

from chat.domain.value_objects.render_tree import RenderTree


@dataclass(frozen=True)
class Text2SqlResult:
    """What the text2sql engine returns for a single question.

    Bundles the natural-language answer, the SQL that produced it, and the
    renderable presentation tree, so the application layer never touches the graph.

    Example:
        Text2SqlResult(response="There are 42 orders.", sql_query="SELECT ...", view=tree)
    """

    response: str
    sql_query: str
    view: RenderTree
