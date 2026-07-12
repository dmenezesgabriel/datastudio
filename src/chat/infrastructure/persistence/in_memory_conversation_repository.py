"""In-memory conversation repository providing short-term chat memory."""

import time

from chat.application.ports.conversation_repository import ConversationRepository
from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.conversation_summary import ConversationSummary


class InMemoryConversationRepository(ConversationRepository):
    """Stores conversations in a dict for the lifetime of the process.

    Short-term memory: state is lost on restart. Suitable for a single-process
    server; swap for a durable adapter (same port) to persist across restarts.

    Example:
        repo = InMemoryConversationRepository()
        repo.save(conversation)
        same = repo.get(conversation.conversation_id, conversation.owner_id)
    """

    def __init__(self) -> None:
        """Start with an empty conversation store and no update timestamps."""
        self._conversations: dict[str, Conversation] = {}
        self._updated_at: dict[str, float] = {}

    def get(self, conversation_id: str, owner_id: str) -> Conversation | None:
        """Return the conversation for the id only when it belongs to ``owner_id``.

        A wrong owner is treated exactly like an absent id (returns None) so a
        caller cannot probe for other users' conversations.
        """
        conversation = self._conversations.get(conversation_id)
        if conversation is None or conversation.owner_id != owner_id:
            return None
        return conversation

    def save(self, conversation: Conversation) -> None:
        """Persist the conversation and stamp its update time (for sidebar ordering)."""
        self._conversations[conversation.conversation_id] = conversation
        self._updated_at[conversation.conversation_id] = time.time()

    def list_summaries(self, owner_id: str) -> list[ConversationSummary]:
        """Summarize ``owner_id``'s conversations, most-recently-updated first."""
        owned = [c for c in self._conversations.values() if c.owner_id == owner_id]
        return sorted((self._summarize(c) for c in owned), key=lambda s: s.updated_at, reverse=True)

    def _summarize(self, conversation: Conversation) -> ConversationSummary:
        """Build a sidebar summary from a stored conversation and its update time."""
        return ConversationSummary(
            conversation_id=conversation.conversation_id,
            title=conversation.title(),
            message_count=len(conversation.messages),
            updated_at=self._updated_at.get(conversation.conversation_id, 0.0),
        )
