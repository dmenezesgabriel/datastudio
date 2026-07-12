"""Port interface for conversation persistence (short-term chat memory)."""

from typing import Protocol, runtime_checkable

from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.conversation_summary import ConversationSummary


@runtime_checkable
class ConversationRepository(Protocol):
    """Contract for storing and retrieving conversations by id.

    The lifetime of stored conversations is an implementation concern: the
    in-memory adapter keeps them for the process lifetime (short-term memory);
    a durable adapter could persist them across restarts.

    Reads are scoped by ``owner_id`` so a caller only ever reaches their own
    conversations; ``save`` needs no owner argument because it travels on the
    conversation entity.

    Example:
        repo: ConversationRepository = InMemoryConversationRepository()
        repo.save(conversation)
        same = repo.get(conversation.conversation_id, conversation.owner_id)
    """

    def get(self, conversation_id: str, owner_id: str) -> Conversation | None:
        """Return the conversation for the id if owned by ``owner_id``, else None.

        Returns None both when the id is absent and when it belongs to another
        user — callers cannot distinguish the two (no cross-user existence leak).
        """
        ...

    def save(self, conversation: Conversation) -> None:
        """Persist the conversation, overwriting any prior state for its id."""
        ...

    def list_summaries(self, owner_id: str) -> list[ConversationSummary]:
        """Return summaries of ``owner_id``'s conversations, most-recently-updated first."""
        ...
