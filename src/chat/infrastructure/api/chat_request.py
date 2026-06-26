"""Request payload for the chat endpoint."""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """A question sent within a conversation.

    The client supplies a stable ``conversation_id`` so follow-up turns accumulate
    in the same conversation (short-term memory).

    Example:
        ChatRequest(conversation_id="c-1", question="How many orders were delivered?")
    """

    conversation_id: str
    question: str
