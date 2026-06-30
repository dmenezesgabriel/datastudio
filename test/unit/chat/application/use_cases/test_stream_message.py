import asyncio
from typing import cast

from chat.application.ports.conversation_repository import ConversationRepository
from chat.application.ports.text2sql_port import Text2SqlPort
from chat.application.use_cases.stream_message import StreamMessage
from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.stream_event import ChatStreamEvent
from test.unit.chat.application.use_cases.fakes import (
    FakeConversationRepository,
    FakeStreamingText2SqlEngine,
    make_events,
)


def _use_case(
    repository: FakeConversationRepository, engine: FakeStreamingText2SqlEngine
) -> StreamMessage:
    return StreamMessage(cast(ConversationRepository, repository), cast(Text2SqlPort, engine))


def _drain(use_case: StreamMessage, cid: str, question: str) -> list[ChatStreamEvent]:
    async def run() -> list[ChatStreamEvent]:
        return [event async for event in use_case.execute(cid, question)]

    return asyncio.run(run())


class TestStreamMessage:
    def test_forwards_engine_events_to_the_caller(self) -> None:
        engine = FakeStreamingText2SqlEngine(make_events())
        events = _drain(_use_case(FakeConversationRepository(), engine), "c-1", "Sales overview")
        assert [type(e).__name__ for e in events] == [
            "WidgetDataReady",
            "ViewPatchLine",
            "SqlReady",
            "NarrativeReady",
        ]
        assert engine.questions == ["Sales overview"]

    def test_persists_both_turns_after_stream_completes(self) -> None:
        repository = FakeConversationRepository()
        engine = FakeStreamingText2SqlEngine(make_events("Revenue grew."))
        _drain(_use_case(repository, engine), "c-1", "overview")
        saved = repository.saved["c-1"]
        assert [m.role for m in saved.messages] == ["user", "assistant"]
        assert saved.messages[1].content == "Revenue grew."

    def test_reuses_existing_conversation(self) -> None:
        repository = FakeConversationRepository()
        existing = Conversation.new("c-1")
        existing.append_user_message("earlier")
        repository.save(existing)
        engine = FakeStreamingText2SqlEngine(make_events("ans"))
        _drain(_use_case(repository, engine), "c-1", "follow-up")
        assert [m.content for m in repository.saved["c-1"].messages] == [
            "earlier",
            "follow-up",
            "ans",
        ]
