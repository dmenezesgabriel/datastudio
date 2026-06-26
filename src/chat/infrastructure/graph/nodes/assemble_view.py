"""LangGraph node that assembles the final json-render tree from the ViewSpec."""

from typing import cast

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.view_spec import ViewSpec
from chat.infrastructure.graph.view.render_tree_builder import (
    assemble_render_tree,
    narrative_tree,
)
from shared.domain.value_objects.query_result import QueryResult


class AssembleView:
    """Node that turns the recommended ViewSpec + result into a renderable tree.

    Pure assembly with no dependencies (satisfies the ChatNode callable protocol).
    On the SQL-failure path — where there is no view_spec or query_result — it emits
    a narrative-only tree so the client always has something to render.

    Example:
        node = AssembleView()
        result = node({"response": "...", "query_result": ..., "view_spec": ...})
        # result == {"view": RenderTree(...)}
    """

    def __call__(self, state: ChatState) -> dict[str, RenderTree]:
        """Assemble the render tree, falling back to narrative-only on failure."""
        data = cast(dict[str, object], state)
        query_result = data.get("query_result")
        view_spec = data.get("view_spec")
        narrative = state["response"]
        if not isinstance(query_result, QueryResult) or not isinstance(view_spec, ViewSpec):
            return {"view": narrative_tree(narrative)}
        return {"view": assemble_render_tree(view_spec, query_result, narrative)}
