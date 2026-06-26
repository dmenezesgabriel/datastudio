from typing import cast

from chat.application.ports.conversation_repository import ConversationRepository
from chat.application.ports.text2sql_port import Text2SqlPort
from chat.application.use_cases.send_message import SendMessage
from chat.domain.entities.conversation import Conversation
from test.unit.chat.application.use_cases.fakes import (
    FakeConversationRepository,
    FakeText2SqlEngine,
    make_result,
)


def _use_case(repository: FakeConversationRepository, engine: FakeText2SqlEngine) -> SendMessage:
    return SendMessage(cast(ConversationRepository, repository), cast(Text2SqlPort, engine))


class TestSendMessage:
    def test_appends_user_then_assistant_and_saves(self) -> None:
        # arrange
        repository = FakeConversationRepository()
        engine = FakeText2SqlEngine(make_result("There are 42 orders."))
        # act
        _use_case(repository, engine).execute("c-1", "How many orders?")
        # assert — both turns persisted in order
        saved = repository.saved["c-1"]
        assert [m.role for m in saved.messages] == ["user", "assistant"]
        assert saved.messages[0].content == "How many orders?"
        assert saved.messages[1].content == "There are 42 orders."

    def test_returns_engine_result(self) -> None:
        # arrange
        result = make_result("answer")
        engine = FakeText2SqlEngine(result)
        # act
        returned = _use_case(FakeConversationRepository(), engine).execute("c-1", "q")
        # assert
        assert returned is result
        assert engine.questions == ["q"]

    def test_reuses_existing_conversation(self) -> None:
        # arrange — a conversation already has one prior round
        repository = FakeConversationRepository()
        existing = Conversation.new("c-1")
        existing.append_user_message("earlier")
        repository.save(existing)
        engine = FakeText2SqlEngine(make_result())
        # act
        _use_case(repository, engine).execute("c-1", "follow-up")
        # assert — new turns append to the same conversation
        assert [m.content for m in repository.saved["c-1"].messages] == [
            "earlier",
            "follow-up",
            "ans",
        ]
