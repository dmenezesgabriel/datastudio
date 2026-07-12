import time

from chat.domain.entities.conversation import Conversation
from chat.infrastructure.persistence.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)

_OWNER = "u-1"


class TestInMemoryConversationRepository:
    def test_save_then_get_round_trip(self) -> None:
        # arrange
        repository = InMemoryConversationRepository()
        conversation = Conversation.new("c-1", _OWNER)
        conversation.append_user_message("hi")
        # act
        repository.save(conversation)
        # assert
        assert repository.get("c-1", _OWNER) is conversation

    def test_get_missing_returns_none(self) -> None:
        # arrange
        repository = InMemoryConversationRepository()
        # act / assert
        assert repository.get("absent", _OWNER) is None

    def test_save_overwrites_prior_state(self) -> None:
        # arrange
        repository = InMemoryConversationRepository()
        repository.save(Conversation.new("c-1", _OWNER))
        updated = Conversation.new("c-1", _OWNER)
        updated.append_user_message("new")
        # act
        repository.save(updated)
        # assert
        stored = repository.get("c-1", _OWNER)
        assert stored is not None
        assert len(stored.messages) == 1

    def test_list_summaries_empty_when_nothing_saved(self) -> None:
        # arrange / act / assert
        assert InMemoryConversationRepository().list_summaries(_OWNER) == []

    def test_list_summaries_titles_and_counts_each_conversation(self) -> None:
        # arrange
        repository = InMemoryConversationRepository()
        conversation = Conversation.new("c-1", _OWNER)
        conversation.append_user_message("How many events?")
        repository.save(conversation)
        # act
        summaries = repository.list_summaries(_OWNER)
        # assert
        assert len(summaries) == 1
        assert summaries[0].conversation_id == "c-1"
        assert summaries[0].title == "How many events?"
        assert summaries[0].message_count == 1

    def test_list_summaries_orders_most_recently_updated_first(self) -> None:
        # arrange — save c-1 then c-2, then re-save c-1 so it becomes the most recent
        repository = InMemoryConversationRepository()
        first = Conversation.new("c-1", _OWNER)
        first.append_user_message("first")
        second = Conversation.new("c-2", _OWNER)
        second.append_user_message("second")
        repository.save(first)
        time.sleep(0.005)  # guarantee a distinct update timestamp for ordering
        repository.save(second)
        time.sleep(0.005)
        repository.save(first)  # touch c-1 last
        # act
        ids = [s.conversation_id for s in repository.list_summaries(_OWNER)]
        # assert
        assert ids == ["c-1", "c-2"]


class TestOwnerScoping:
    """A caller only ever reaches their own conversations (no cross-user leak)."""

    def test_get_returns_none_for_another_users_conversation(self) -> None:
        # arrange — a conversation owned by alice
        repository = InMemoryConversationRepository()
        repository.save(Conversation.new("c-1", "alice"))
        # act / assert — bob cannot fetch it, and can't tell it apart from absent
        assert repository.get("c-1", "bob") is None

    def test_list_summaries_excludes_other_users_conversations(self) -> None:
        # arrange — one conversation each for alice and bob
        repository = InMemoryConversationRepository()
        alices = Conversation.new("c-a", "alice")
        alices.append_user_message("alice")
        bobs = Conversation.new("c-b", "bob")
        bobs.append_user_message("bob")
        repository.save(alices)
        repository.save(bobs)
        # act
        ids = [s.conversation_id for s in repository.list_summaries("alice")]
        # assert — alice sees only her own thread
        assert ids == ["c-a"]
