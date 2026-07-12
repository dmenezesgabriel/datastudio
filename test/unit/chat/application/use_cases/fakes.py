from collections.abc import AsyncIterator, Sequence

from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.conversation_summary import ConversationSummary
from chat.domain.value_objects.message import Message
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    SqlReady,
    ViewPatchLine,
    WidgetDataReady,
)
from shared.domain.value_objects.query_result import QueryResult


class FakeConversationRepository:
    """In-test conversation store recording saves keyed by id, scoped by owner."""

    def __init__(self) -> None:
        self.saved: dict[str, Conversation] = {}

    def get(self, conversation_id: str, owner_id: str) -> Conversation | None:
        conversation = self.saved.get(conversation_id)
        if conversation is None or conversation.owner_id != owner_id:
            return None
        return conversation

    def save(self, conversation: Conversation) -> None:
        self.saved[conversation.conversation_id] = conversation

    def list_summaries(self, owner_id: str) -> list[ConversationSummary]:
        return [
            ConversationSummary(
                conversation_id=c.conversation_id,
                title=c.title(),
                message_count=len(c.messages),
                updated_at=0.0,
            )
            for c in self.saved.values()
            if c.owner_id == owner_id
        ]


class FakeStreamingText2SqlEngine:
    """Engine yielding fixed stream events and recording questions asked."""

    def __init__(self, events: list[ChatStreamEvent]) -> None:
        self._events = events
        self.questions: list[str] = []
        self.histories: list[Sequence[Message]] = []

    async def stream(
        self, question: str, history: Sequence[Message]
    ) -> AsyncIterator[ChatStreamEvent]:
        self.questions.append(question)
        self.histories.append(history)
        for event in self._events:
            yield event


def make_events(response: str = "Summary.") -> list[ChatStreamEvent]:
    """Build a representative one-widget event stream: data, view, sql, then narrative."""
    result = QueryResult(columns=["n"], rows=[(42,)], row_count=1)
    return [
        WidgetDataReady(widget_id="widget-0", result=result),
        ViewPatchLine(
            line='{"op":"add","path":"/elements/widget-0-table","value":{"type":"DataTable"}}'
        ),
        SqlReady(widget_id="widget-0", sql="SELECT 1"),
        NarrativeReady(text=response),
    ]
