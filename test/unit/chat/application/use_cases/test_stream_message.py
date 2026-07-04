import asyncio
import logging
from typing import cast

from chat.application.ports.conversation_repository import ConversationRepository
from chat.application.ports.text2sql_port import Text2SqlPort
from chat.application.use_cases.stream_message import StreamMessage
from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.stream_event import ChatStreamEvent, SqlReady, WidgetDataReady
from chat.domain.value_objects.text2sql_result import Text2SqlResult
from chat.infrastructure.api.dashboard_view_builder import DashboardViewBuilder
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.application.use_cases.fakes import (
    FakeConversationRepository,
    FakeStreamingText2SqlEngine,
    make_events,
)


def _use_case(
    repository: FakeConversationRepository, engine: FakeStreamingText2SqlEngine
) -> StreamMessage:
    return StreamMessage(
        cast(ConversationRepository, repository),
        cast(Text2SqlPort, engine),
        DashboardViewBuilder(),
        logging.getLogger("test.stream_message"),
    )


def _result(response: str) -> Text2SqlResult:
    view = RenderTree(
        root="root", elements={"root": RenderElement(type="Stack", props={}, children=[])}
    )
    return Text2SqlResult(narrative=response, view=view)


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

    def test_new_conversation_forwards_empty_history(self) -> None:
        engine = FakeStreamingText2SqlEngine(make_events())
        _drain(_use_case(FakeConversationRepository(), engine), "c-1", "first question")
        # A brand-new conversation has no prior turns to inject.
        assert list(engine.histories[0]) == []

    def test_forwards_prior_turns_without_duplicating_current_question(self) -> None:
        # arrange — a conversation with one completed exchange already recorded
        repository = FakeConversationRepository()
        existing = Conversation.new("c-1")
        existing.append_user_message("earlier")
        existing.append_assistant_message(_result("earlier answer"))
        repository.save(existing)
        engine = FakeStreamingText2SqlEngine(make_events("ans"))
        # act
        _drain(_use_case(repository, engine), "c-1", "follow-up")
        # assert — the window is the prior turns only; "follow-up" is passed as the
        # question, never injected into history (which would double-count it).
        assert [m.content for m in engine.histories[0]] == ["earlier", "earlier answer"]
        assert engine.questions == ["follow-up"]

    def test_does_not_persist_assistant_turn_when_no_narrative_ready(self) -> None:
        # Engine emits data and SQL but no NarrativeReady — nothing to remember.
        result = QueryResult(columns=["n"], rows=[(1,)], row_count=1)
        events: list[ChatStreamEvent] = [
            WidgetDataReady(widget_id="w0", result=result),
            SqlReady(widget_id="w0", sql_query="SELECT 1"),
        ]
        repository = FakeConversationRepository()
        _drain(_use_case(repository, FakeStreamingText2SqlEngine(events)), "c-1", "q")
        saved = repository.saved["c-1"]
        assert [m.role for m in saved.messages] == ["user"]

    def test_persists_narrative_render_tree_with_response_text(self) -> None:
        # Narrative view must be a Markdown tree whose text matches the response.
        repository = FakeConversationRepository()
        _drain(
            _use_case(repository, FakeStreamingText2SqlEngine(make_events("42 orders."))),
            "c-1",
            "q",
        )
        view = repository.saved["c-1"].messages[1].view
        assert view is not None
        assert view.root == "root"
        assert "narrative" in view.elements
        narrative = view.elements["narrative"]
        assert narrative.type == "Markdown"
        assert narrative.props.get("text") == "42 orders."

    def test_persists_full_dashboard_widgets_and_state_for_reopen(self) -> None:
        # Regression: reopening a thread must re-render charts/tables, not just text — so
        # the persisted view carries the widget element AND its $state data.
        repository = FakeConversationRepository()
        _drain(_use_case(repository, FakeStreamingText2SqlEngine(make_events("Rev."))), "c-1", "q")
        view = repository.saved["c-1"].messages[1].view
        assert view is not None
        assert "widget-0-table" in view.elements  # the LLM-authored widget, not just narrative
        assert view.state == {"widget-0": {"columns": ["n"], "rows": [{"n": 42}]}}
