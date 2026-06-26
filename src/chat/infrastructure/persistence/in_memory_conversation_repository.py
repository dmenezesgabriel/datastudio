"""In-memory conversation repository providing short-term chat memory."""

from chat.application.ports.conversation_repository import ConversationRepository
from chat.domain.entities.conversation import Conversation


class InMemoryConversationRepository(ConversationRepository):
    """Stores conversations in a dict for the lifetime of the process.

    Short-term memory: state is lost on restart. Suitable for a single-process
    server; swap for a durable adapter (same port) to persist across restarts.

    Example:
        repo = InMemoryConversationRepository()
        repo.save(conversation)
        same = repo.get(conversation.conversation_id)
    """

    def __init__(self) -> None:
        """Start with an empty conversation store."""
        self._conversations: dict[str, Conversation] = {}

    def get(self, conversation_id: str) -> Conversation | None:
        """Return the stored conversation for the id, or None if absent."""
        return self._conversations.get(conversation_id)

    def save(self, conversation: Conversation) -> None:
        """Persist the conversation, overwriting any prior state for its id."""
        self._conversations[conversation.conversation_id] = conversation
