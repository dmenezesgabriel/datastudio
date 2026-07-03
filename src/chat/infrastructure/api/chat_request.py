"""Request payload for the streaming chat endpoint.

Matches the body json-render's ``useUIStream`` hook POSTs: ``{prompt, context,
currentSpec}``. ``currentSpec`` is the client's in-progress spec; the server builds
a fresh one each turn, so it is intentionally not declared (pydantic ignores it).
"""

from pydantic import BaseModel, Field


class StreamChatRequest(BaseModel):
    """A question (``prompt``) plus an open ``context`` carrying ``conversation_id``.

    The client supplies a stable ``conversation_id`` in ``context`` so follow-up
    turns accumulate in the same conversation (short-term memory).

    Example:
        StreamChatRequest(prompt="How many events?", context={"conversation_id": "c-1"})
    """

    prompt: str
    context: dict[str, object] = Field(default_factory=dict)
