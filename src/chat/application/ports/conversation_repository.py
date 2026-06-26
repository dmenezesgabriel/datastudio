"""Port interface for conversation persistence (short-term chat memory)."""

from typing import Protocol, runtime_checkable

from chat.domain.entities.conversation import Conversation


@runtime_checkable
class ConversationRepository(Protocol):
    """Contract for storing and retrieving conversations by id.

    The lifetime of stored conversations is an implementation concern: the
    in-memory adapter keeps them for the process lifetime (short-term memory);
    a durable adapter could persist them across restarts.

    Example:
        repo: ConversationRepository = InMemoryConversationRepository()
        repo.save(conversation)
        same = repo.get(conversation.conversation_id)
    """

    def get(self, conversation_id: str) -> Conversation | None:
        """Return the stored conversation for the id, or None if absent."""
        ...

    def save(self, conversation: Conversation) -> None:
        """Persist the conversation, overwriting any prior state for its id."""
        ...
