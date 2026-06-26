from chat.domain.entities.conversation import Conversation
from chat.infrastructure.persistence.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)


class TestInMemoryConversationRepository:
    def test_save_then_get_round_trip(self) -> None:
        # arrange
        repository = InMemoryConversationRepository()
        conversation = Conversation.new("c-1")
        conversation.append_user_message("hi")
        # act
        repository.save(conversation)
        # assert
        assert repository.get("c-1") is conversation

    def test_get_missing_returns_none(self) -> None:
        # arrange
        repository = InMemoryConversationRepository()
        # act / assert
        assert repository.get("absent") is None

    def test_save_overwrites_prior_state(self) -> None:
        # arrange
        repository = InMemoryConversationRepository()
        repository.save(Conversation.new("c-1"))
        updated = Conversation.new("c-1")
        updated.append_user_message("new")
        # act
        repository.save(updated)
        # assert
        stored = repository.get("c-1")
        assert stored is not None
        assert len(stored.messages) == 1
