"""Tests for EditDashboardAdapter.edit — edit-node updates mapped to patch events.

Mirrors test_text2sql_engine_adapter_stream.py: same collaborator (a fake compiled
graph), same event vocabulary. The edit path differs in that it carries no conversation
memory — the current spec seeds the graph as ``prior_spec`` instead.
"""

import asyncio
from typing import cast

from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    ProgressStep,
    SqlReady,
    WidgetDataReady,
)
from chat.domain.value_objects.widget import WidgetResult
from chat.infrastructure.graph.edit_dashboard_adapter import EditDashboardAdapter
from chat.infrastructure.graph.types import TypedChatGraph
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.fake_chat_graph import FakeStreamingChatGraph


def _spec() -> RenderTree:
    return RenderTree(
        root="root", elements={"root": RenderElement(type="Stack", props={}, children=[])}
    )


def _widget_result(widget_id: str, value: int) -> WidgetResult:
    return WidgetResult(
        widget_id=widget_id,
        title="T",
        result=QueryResult(columns=["n"], rows=[(value,)], row_count=1),
        sql=f"SELECT {value}",
    )


def _view_line(widget_id: str) -> str:
    return f'{{"op":"replace","path":"/elements/{widget_id}-chart","value":{{"type":"ChartJs"}}}}'


def _adapter(graph: FakeStreamingChatGraph, timeout_s: float | None = None) -> EditDashboardAdapter:
    return EditDashboardAdapter(cast(TypedChatGraph, graph), timeout_s=timeout_s)


def _collect(adapter: EditDashboardAdapter, instruction: str) -> list[ChatStreamEvent]:
    async def run() -> list[ChatStreamEvent]:
        return [event async for event in adapter.edit(_spec(), instruction)]

    return asyncio.run(run())


class TestEditPatchEmittingNodes:
    """author_edit_patches (restyle) and build_widget (reanalyze) share the mapping."""

    def test_restyle_node_yields_only_view_patches(self) -> None:
        # arrange — a restyle rewrites the view without re-running SQL
        chunks = [{"author_edit_patches": {"widget_patch_lines": [_view_line("widget-0")]}}]
        # act
        events = _collect(_adapter(FakeStreamingChatGraph(chunks)), "make it blue")
        # assert
        assert [type(e).__name__ for e in events] == ["ViewPatchLine"]

    def test_reanalyze_node_yields_data_then_view_then_sql(self) -> None:
        # arrange — a rebuilt widget carries fresh data alongside its view
        chunks = [
            {
                "build_widget": {
                    "widget_patch_lines": [_view_line("widget-0")],
                    "widget_results": [_widget_result("widget-0", 42)],
                }
            }
        ]
        # act
        events = _collect(_adapter(FakeStreamingChatGraph(chunks)), "use last 30 days")
        # assert — data first so $state exists when the view binds
        assert [type(e).__name__ for e in events] == [
            "WidgetDataReady",
            "ViewPatchLine",
            "SqlReady",
        ]

    def test_rebuilt_widget_carries_its_id_and_rows(self) -> None:
        chunks = [
            {
                "build_widget": {
                    "widget_patch_lines": [],
                    "widget_results": [_widget_result("widget-1", 7)],
                }
            }
        ]
        events = _collect(_adapter(FakeStreamingChatGraph(chunks)), "recount")
        data = next(e for e in events if isinstance(e, WidgetDataReady))
        sql = next(e for e in events if isinstance(e, SqlReady))
        assert (data.widget_id, data.result.rows[0][0]) == ("widget-1", 7)
        assert (sql.widget_id, sql.sql) == ("widget-1", "SELECT 7")


class TestEditMultiNodeChunk:
    def test_every_node_in_one_chunk_is_surfaced(self) -> None:
        # LangGraph puts one key per node that finished in the same superstep, so a
        # fanned-out chunk carries several. Accumulating (not overwriting) is what keeps
        # the earlier nodes' patches from being dropped.
        chunks = [
            {
                "author_edit_patches": {"widget_patch_lines": [_view_line("widget-0")]},
                "build_widget": {
                    "widget_patch_lines": [_view_line("widget-1")],
                    "widget_results": [_widget_result("widget-1", 7)],
                },
            }
        ]
        events = _collect(_adapter(FakeStreamingChatGraph(chunks)), "edit both")
        assert [type(e).__name__ for e in events] == [
            "ViewPatchLine",  # author_edit_patches — must survive the later node
            "WidgetDataReady",
            "ViewPatchLine",
            "SqlReady",
        ]


class TestEditSilentNodes:
    def test_non_patch_node_update_yields_nothing(self) -> None:
        # classify_edit decides the route; it emits no patch of its own
        chunks = [{"classify_edit": {"edit_mode": "restyle"}}]
        assert _collect(_adapter(FakeStreamingChatGraph(chunks)), "tweak it") == []


class TestEditProgress:
    def test_forwards_custom_progress_steps(self) -> None:
        chunks = [
            ("custom", ProgressStep(step_id="classify_edit", label="Reading", status="running")),
            {"author_edit_patches": {"widget_patch_lines": [_view_line("widget-0")]}},
        ]
        events = _collect(_adapter(FakeStreamingChatGraph(chunks)), "restyle")
        steps = [(e.step_id, e.status) for e in events if isinstance(e, ProgressStep)]
        assert steps == [("classify_edit", "running")]

    def test_requests_both_update_and_custom_stream_modes(self) -> None:
        # Asking for "updates" alone would silently drop every live ProgressStep
        # rather than fail, so the stream_mode pair is pinned explicitly.
        graph = FakeStreamingChatGraph([])
        _collect(_adapter(graph), "restyle")
        assert graph.last_kwargs["stream_mode"] == ["updates", "custom"]


class TestEditSeedsPriorSpec:
    def test_current_spec_and_instruction_seed_the_graph(self) -> None:
        # arrange
        graph = FakeStreamingChatGraph([])

        # act
        _collect(_adapter(graph), "reorder the widgets")

        # assert — the whole edit state is the prior spec; no conversation memory
        seeded = cast(dict[str, object], graph.last_input)
        assert seeded["prior_spec"] == _spec()
        assert seeded["instruction"] == "reorder the widgets"
        assert seeded["question"] == "reorder the widgets"
        assert seeded["history"] == []

    def test_each_edit_gets_its_own_request_id(self) -> None:
        graph = FakeStreamingChatGraph([])
        _collect(_adapter(graph), "first")
        first = cast(dict[str, object], graph.last_input)["request_id"]
        _collect(_adapter(graph), "second")
        second = cast(dict[str, object], graph.last_input)["request_id"]
        assert first != second


class TestEditTimeout:
    def test_yields_graceful_narrative_when_too_slow(self) -> None:
        chunks = [{"author_edit_patches": {"widget_patch_lines": [_view_line("widget-0")]}}]
        graph = FakeStreamingChatGraph(chunks, delay_s=0.05)
        events = _collect(_adapter(graph, timeout_s=0.01), "slow edit")
        assert isinstance(events[-1], NarrativeReady)
        assert "longer than expected" in events[-1].text

    def test_no_timeout_budget_lets_a_slow_edit_finish(self) -> None:
        # timeout_s=None disables the budget (the eval runner's configuration)
        chunks = [{"author_edit_patches": {"widget_patch_lines": [_view_line("widget-0")]}}]
        graph = FakeStreamingChatGraph(chunks, delay_s=0.05)
        events = _collect(_adapter(graph, timeout_s=None), "slow but allowed")
        assert [type(e).__name__ for e in events] == ["ViewPatchLine"]
