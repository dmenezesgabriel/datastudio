"""Conversation aggregate: an identified, ordered sequence of message turns."""

from chat.domain.value_objects.message import Message
from chat.domain.value_objects.text2sql_result import Text2SqlResult


class Conversation:
    """A chat conversation identified by ``conversation_id``.

    Holds the ordered turns and grows by appending user questions and the
    assistant answers produced for them. Short-term memory: persistence lifetime
    is owned by the repository, not this entity.

    Example:
        conv = Conversation.new("c-1")
        conv.append_user_message("How many orders?")
        msg = conv.append_assistant_message(result)
    """

    def __init__(self, conversation_id: str, messages: list[Message]) -> None:
        """Build a conversation from its id and existing turns."""
        self.conversation_id = conversation_id
        self.messages = messages

    @classmethod
    def new(cls, conversation_id: str) -> "Conversation":
        """Start an empty conversation with the given id."""
        return cls(conversation_id, [])

    def append_user_message(self, question: str) -> Message:
        """Append the user's question turn and return it."""
        message = Message(role="user", content=question, view=None)
        self.messages.append(message)
        return message

    def append_assistant_message(self, result: Text2SqlResult) -> Message:
        """Append the assistant turn built from an engine result and return it."""
        message = Message(role="assistant", content=result.response, view=result.view)
        self.messages.append(message)
        return message
