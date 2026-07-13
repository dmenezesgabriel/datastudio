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


def _widget_view_lines(widget_id: str, leaf: str, kind: str, region: str, title: str) -> list[str]:
    """The namespaced frame+leaf patch lines one build_widget worker emits (as authored)."""
    leaf_id = f"{widget_id}-{leaf}"
    frame_id = f"{widget_id}-frame"
    binding = f'"data":{{"$state":"/{widget_id}/rows"}}'
    leaf_el = f'{{"type":"{kind}","props":{{{title},{binding}}},"children":[]}}'
    frame_el = f'{{"type":"WidgetFrame","props":{{"sql":""}},"children":["{leaf_id}"]}}'
    return [
        f'{{"op":"add","path":"/elements/{leaf_id}","value":{leaf_el}}}',
        f'{{"op":"add","path":"/elements/{frame_id}","value":{frame_el}}}',
        f'{{"op":"add","path":"/elements/{region}/children/-","value":"{frame_id}"}}',
    ]


def _widget_events(
    widget_id: str, leaf: str, kind: str, region: str, title: str, result: QueryResult, sql: str
) -> list[ChatStreamEvent]:
    """One widget's full event group: data, framed view lines, then its SQL."""
    events: list[ChatStreamEvent] = [WidgetDataReady(widget_id=widget_id, result=result)]
    events += [
        ViewPatchLine(line=ln) for ln in _widget_view_lines(widget_id, leaf, kind, region, title)
    ]
    events.append(SqlReady(widget_id=widget_id, sql=sql))
    return events


def make_dashboard_events(response: str = "Overview.") -> list[ChatStreamEvent]:
    """Build a realistic two-widget dashboard stream (a KPI + a chart, each framed).

    Mirrors what two ``build_widget`` workers emit, so ``DashboardViewBuilder`` compiles a
    tree with ``widget-0-frame``/``widget-1-frame`` — the shape the artifact split reads.
    """
    kpi = QueryResult(columns=["c"], rows=[(42,)], row_count=1)
    chart = QueryResult(columns=["g", "n"], rows=[("Drama", 789)], row_count=1)
    events = _widget_events(
        "widget-0", "kpi", "KpiStat", "kpi-row", '"label":"Total"', kpi, "SELECT c"
    )
    events += _widget_events(
        "widget-1", "chart", "ChartJs", "grid", '"title":"By genre"', chart, "SELECT g"
    )
    events.append(NarrativeReady(text=response))
    return events
