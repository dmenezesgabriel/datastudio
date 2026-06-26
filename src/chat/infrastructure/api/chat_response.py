"""Response payload for the chat endpoint."""

from pydantic import BaseModel

from chat.domain.value_objects.render_tree import RenderTree


class ChatResponse(BaseModel):
    """The assistant's answer plus the renderable presentation tree.

    ``response`` is the plain narrative (for clients that do not render the tree);
    ``view`` is the json-render spec the frontend renders; ``sql_query`` is exposed
    for transparency/debugging.

    Example:
        ChatResponse(conversation_id="c-1", response="There are 42 orders.",
                     sql_query="SELECT ...", view=tree)
    """

    conversation_id: str
    response: str
    sql_query: str
    view: RenderTree
