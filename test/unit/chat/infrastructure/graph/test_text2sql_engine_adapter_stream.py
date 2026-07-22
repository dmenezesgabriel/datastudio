"""Tests for Text2SqlEngineAdapter.stream — fan-out updates mapped to per-widget events."""

import asyncio
from typing import cast

from chat.domain.value_objects.message import Message
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    ProgressStep,
    SqlReady,
    WidgetDataReady,
)
from chat.domain.value_objects.widget import WidgetResult
from chat.infrastructure.graph.text2sql_engine_adapter import Text2SqlEngineAdapter
from chat.infrastructure.graph.types import TypedChatGraph
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.fake_chat_graph import FakeStreamingChatGraph


def _result(value: int) -> QueryResult:
    return QueryResult(columns=["n"], rows=[(value,)], row_count=1)


def _widget_result(widget_id: str, value: int) -> WidgetResult:
    return WidgetResult(
        widget_id=widget_id, title="T", result=_result(value), sql=f"SELECT {value}"
    )


def _widget_chunk(widget_id: str, value: int) -> dict[str, object]:
    line = f'{{"op":"add","path":"/elements/{widget_id}-chart","value":{{"type":"ChartJs"}}}}'
    return {
        "build_widget": {
            "widget_patch_lines": [line],
            "widget_results": [_widget_result(widget_id, value)],
        }
    }


def _chunks() -> list[object]:
    # updates chunks (plain dicts) mixed with a custom progress chunk (a tuple), as
    # LangGraph yields under stream_mode=["updates", "custom"].
    return [
        {"list_tables": {"tables": ["orders"]}},
        ("custom", ProgressStep(step_id="plan_widgets", label="Planning", status="running")),
        {"plan_widgets": {"widget_specs": []}},
        _widget_chunk("widget-0", 42),
        _widget_chunk("widget-1", 7),
        {"compose_narrative": {"narrative": "Two widgets summarized."}},
    ]


def _adapter(
    graph: FakeStreamingChatGraph, timeout_s: float | None = None
) -> Text2SqlEngineAdapter:
    return Text2SqlEngineAdapter(cast(TypedChatGraph, graph), timeout_s=timeout_s)


def _collect(adapter: Text2SqlEngineAdapter, question: str) -> list[ChatStreamEvent]:
    async def run() -> list[ChatStreamEvent]:
        return [event async for event in adapter.stream(question, [])]

    return asyncio.run(run())


class TestStreamHappyPath:
    def test_event_sequence_streams_each_widget_then_narrative(self) -> None:
        events = _collect(_adapter(FakeStreamingChatGraph(_chunks())), "overview")
        assert [type(e).__name__ for e in events] == [
            "ProgressStep",  # custom progress (plan_widgets running)
            "WidgetDataReady",  # widget-0 data (/state patch)
            "ViewPatchLine",  # widget-0 view
            "SqlReady",  # widget-0 sql
            "WidgetDataReady",  # widget-1 data
            "ViewPatchLine",
            "SqlReady",
            "NarrativeReady",  # overall summary, last
        ]

    def test_widget_data_carries_id_and_rows(self) -> None:
        events = _collect(_adapter(FakeStreamingChatGraph(_chunks())), "q")
        data = [e for e in events if isinstance(e, WidgetDataReady)]
        assert [(d.widget_id, d.result.rows[0][0]) for d in data] == [
            ("widget-0", 42),
            ("widget-1", 7),
        ]

    def test_sql_is_per_widget(self) -> None:
        events = _collect(_adapter(FakeStreamingChatGraph(_chunks())), "q")
        sql = [(e.widget_id, e.sql) for e in events if isinstance(e, SqlReady)]
        assert sql == [("widget-0", "SELECT 42"), ("widget-1", "SELECT 7")]

    def test_narrative_is_the_summary(self) -> None:
        events = _collect(_adapter(FakeStreamingChatGraph(_chunks())), "q")
        assert (
            next(e for e in events if isinstance(e, NarrativeReady)).text
            == "Two widgets summarized."
        )

    def test_forwards_custom_progress_steps(self) -> None:
        events = _collect(_adapter(FakeStreamingChatGraph(_chunks())), "q")
        steps = [(e.step_id, e.status) for e in events if isinstance(e, ProgressStep)]
        assert steps == [("plan_widgets", "running")]

    def test_requests_both_update_and_custom_stream_modes(self) -> None:
        # Asking for "updates" alone would silently drop every live ProgressStep
        # rather than fail, so the stream_mode pair is pinned explicitly.
        graph = FakeStreamingChatGraph(_chunks())
        _collect(_adapter(graph), "q")
        assert graph.last_kwargs["stream_mode"] == ["updates", "custom"]


class TestStreamMultiNodeChunk:
    def test_every_node_in_one_chunk_is_surfaced(self) -> None:
        # Widgets fan out in parallel, so one superstep's chunk carries several node
        # keys. Accumulating (not overwriting) is what keeps the earlier widget's
        # patches from being dropped.
        chunks = [
            {
                "build_widget": {
                    "widget_patch_lines": [
                        '{"op":"add","path":"/elements/widget-0-chart","value":{"type":"ChartJs"}}'
                    ],
                    "widget_results": [_widget_result("widget-0", 42)],
                },
                "compose_narrative": {"narrative": "Summarized."},
            }
        ]
        events = _collect(_adapter(FakeStreamingChatGraph(chunks)), "q")
        assert [type(e).__name__ for e in events] == [
            "WidgetDataReady",  # build_widget — must survive the later node
            "ViewPatchLine",
            "SqlReady",
            "NarrativeReady",
        ]


class TestStreamSeedsHistory:
    def test_history_is_converted_to_messages_in_initial_state(self) -> None:
        # arrange — a prior exchange handed to the engine as short-term memory
        graph = FakeStreamingChatGraph(_chunks())
        history = [
            Message(role="user", content="prior q", view=None),
            Message(role="assistant", content="prior a", view=None),
        ]

        # act
        async def run() -> None:
            async for _ in _adapter(graph).stream("now", history):
                pass

        asyncio.run(run())
        # assert — history reaches the graph as LangChain messages; question is current
        seeded = cast(dict[str, object], graph.last_input)
        assert [type(m).__name__ for m in cast(list[object], seeded["history"])] == [
            "HumanMessage",
            "AIMessage",
        ]
        assert seeded["question"] == "now"


class TestStreamTextBranch:
    def test_answer_text_update_streams_a_single_narrative(self) -> None:
        # the text-only branch: answer_text writes the response, no widgets ran
        chunks = [{"answer_text": {"narrative": "I can query your data."}}]
        events = _collect(_adapter(FakeStreamingChatGraph(chunks)), "what can you do?")
        assert [type(e).__name__ for e in events] == ["NarrativeReady"]
        assert cast(NarrativeReady, events[0]).text == "I can query your data."


class TestStreamFailedWidget:
    def test_failed_widget_yields_only_its_note_view(self) -> None:
        # a build_widget that produced a note (no widget_results) → just the view line
        note = '{"op":"add","path":"/elements/widget-0-note","value":{"type":"Markdown"}}'
        chunks = [{"build_widget": {"widget_patch_lines": [note]}}]
        events = _collect(_adapter(FakeStreamingChatGraph(chunks)), "q")
        assert [type(e).__name__ for e in events] == ["ViewPatchLine"]


class TestStreamTimeout:
    def test_yields_graceful_narrative_when_too_slow(self) -> None:
        graph = FakeStreamingChatGraph(_chunks(), delay_s=0.05)
        events = _collect(_adapter(graph, timeout_s=0.01), "slow")
        assert isinstance(events[-1], NarrativeReady)
        assert "longer than expected" in events[-1].text
