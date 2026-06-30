"""Tests for Text2SqlEngineAdapter.stream — fan-out updates mapped to per-widget events."""

import asyncio
from typing import cast

from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    ProgressUpdate,
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
            "widget_views": [line],
            "widget_results": [_widget_result(widget_id, value)],
        }
    }


def _chunks() -> list[dict[str, object]]:
    return [
        {"list_tables": {"tables": ["orders"]}},
        {"plan_widgets": {"widget_specs": []}},
        _widget_chunk("widget-0", 42),
        _widget_chunk("widget-1", 7),
        {"compose_narrative": {"response": "Two widgets summarized."}},
    ]


def _adapter(
    graph: FakeStreamingChatGraph, timeout_s: float | None = None
) -> Text2SqlEngineAdapter:
    return Text2SqlEngineAdapter(cast(TypedChatGraph, graph), timeout_s=timeout_s)


def _collect(adapter: Text2SqlEngineAdapter, question: str) -> list[ChatStreamEvent]:
    async def run() -> list[ChatStreamEvent]:
        return [event async for event in adapter.stream(question)]

    return asyncio.run(run())


class TestStreamHappyPath:
    def test_event_sequence_streams_each_widget_then_narrative(self) -> None:
        events = _collect(_adapter(FakeStreamingChatGraph(_chunks())), "overview")
        assert [type(e).__name__ for e in events] == [
            "ProgressUpdate",  # list_tables
            "ProgressUpdate",  # plan_widgets
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
        sql = [(e.widget_id, e.sql_query) for e in events if isinstance(e, SqlReady)]
        assert sql == [("widget-0", "SELECT 42"), ("widget-1", "SELECT 7")]

    def test_narrative_is_the_summary(self) -> None:
        events = _collect(_adapter(FakeStreamingChatGraph(_chunks())), "q")
        assert (
            next(e for e in events if isinstance(e, NarrativeReady)).text
            == "Two widgets summarized."
        )

    def test_progress_forwards_node_names(self) -> None:
        events = _collect(_adapter(FakeStreamingChatGraph(_chunks())), "q")
        assert [e.stage for e in events if isinstance(e, ProgressUpdate)] == [
            "list_tables",
            "plan_widgets",
        ]


class TestStreamFailedWidget:
    def test_failed_widget_yields_only_its_note_view(self) -> None:
        # a build_widget that produced a note (no widget_results) → just the view line
        note = '{"op":"add","path":"/elements/widget-0-note","value":{"type":"Markdown"}}'
        chunks = [{"build_widget": {"widget_views": [note]}}]
        events = _collect(_adapter(FakeStreamingChatGraph(chunks)), "q")
        assert [type(e).__name__ for e in events] == ["ViewPatchLine"]


class TestStreamTimeout:
    def test_yields_graceful_narrative_when_too_slow(self) -> None:
        graph = FakeStreamingChatGraph(_chunks(), delay_s=0.05)
        events = _collect(_adapter(graph, timeout_s=0.01), "slow")
        assert isinstance(events[-1], NarrativeReady)
        assert "longer than expected" in events[-1].text
